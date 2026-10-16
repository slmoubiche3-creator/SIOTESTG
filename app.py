"""Small standard-library web server for the request-triage demo."""

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import db


STATUSES = {"Nouveau", "En cours", "En attente", "Résolu"}
STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_BODY_BYTES = 2 * 1024 * 1024


def _send_json(handler, status, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def _read_json(handler):
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        raise ValueError("Invalid Content-Length")
    if length < 0 or length > MAX_BODY_BYTES:
        raise ValueError("Request body is too large")
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Request body must be valid JSON")


def create_server(db_path, intake_token=None, host="127.0.0.1", port=0):
    db.init_db(db_path)

    class RequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format_string, *args):
            return

        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path == "/api/messages":
                query = parse_qs(parsed.query)
                needs_review = query.get("needs_review", [None])[0]
                if needs_review not in (None, "true", "false", "1", "0"):
                    _send_json(self, 400, {"error": "needs_review must be true or false"})
                    return
                messages = db.list_messages(
                    team=query.get("team", [None])[0],
                    status=query.get("status", [None])[0],
                    urgency=query.get("urgency", [None])[0],
                    needs_review=None if needs_review is None else needs_review in ("true", "1"),
                    query=query.get("q", [None])[0],
                )
                _send_json(self, 200, {"messages": messages})
                return
            if parsed.path == "/api/summary":
                _send_json(self, 200, db.get_summary())
                return
            if parsed.path == "/" or parsed.path.startswith("/static/"):
                self._serve_static(parsed.path)
                return
            _send_json(self, 404, {"error": "Not found"})

        def do_POST(self):
            parsed = urlsplit(self.path)
            if parsed.path != "/api/intake":
                _send_json(self, 404, {"error": "Not found"})
                return
            token = self.server.intake_token
            if token:
                expected = "Bearer " + token
                if self.headers.get("Authorization") != expected:
                    _send_json(self, 401, {"error": "A valid intake token is required"})
                    return
            try:
                payload = _read_json(self)
                records = payload.get("messages") if isinstance(payload, dict) else None
                if not isinstance(records, list) or not records:
                    raise ValueError("messages must be a non-empty list")
                if any(not isinstance(record, dict) for record in records):
                    raise ValueError("each message must be an object")
                ids = [db.insert_message(record) for record in records]
            except ValueError as error:
                _send_json(self, 400, {"error": str(error)})
                return
            summary = db.get_summary()
            _send_json(
                self,
                201,
                {"count": len(ids), "ids": ids, "alerts": summary["critical"]},
            )

        def do_PATCH(self):
            match = re.fullmatch(r"/api/messages/(\d+)", urlsplit(self.path).path)
            if not match:
                _send_json(self, 404, {"error": "Not found"})
                return
            try:
                updates = _read_json(self)
                if not isinstance(updates, dict) or not updates:
                    raise ValueError("At least one update is required")
                if not set(updates).issubset({"assignee", "status"}):
                    raise ValueError("Only assignee and status can be updated")
                if "status" in updates and updates["status"] not in STATUSES:
                    raise ValueError("Invalid status")
                if "assignee" in updates and not isinstance(updates["assignee"], str):
                    raise ValueError("Assignee must be text")
                message = db.update_message(int(match.group(1)), updates)
            except ValueError as error:
                _send_json(self, 400, {"error": str(error)})
                return
            if message is None:
                _send_json(self, 404, {"error": "Message not found"})
                return
            _send_json(self, 200, {"message": message})

        def _serve_static(self, request_path):
            if request_path == "/":
                target = STATIC_DIR / "index.html"
            else:
                relative = unquote(request_path[len("/static/"):])
                target = (STATIC_DIR / relative).resolve()
                if STATIC_DIR.resolve() not in target.parents:
                    _send_json(self, 404, {"error": "Not found"})
                    return
            if not target.is_file():
                _send_json(self, 404, {"error": "Not found"})
                return
            content_type = {
                ".html": "text/html; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8",
            }.get(target.suffix, "application/octet-stream")
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer((host, port), RequestHandler)
    server.intake_token = intake_token
    return server


def main():
    database_path = os.environ.get("DATABASE_PATH", "data/requests.sqlite3")
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    token = os.environ.get("INTAKE_TOKEN")
    server = create_server(database_path, intake_token=token, host=host, port=port)
    print("Request triage is available at http://%s:%s" % (host, server.server_port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
