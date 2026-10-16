import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import app
import db


def request_json(url, method="GET", payload=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


class RequestApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = self.temp_dir.name + "/requests.sqlite3"
        self.server = app.create_server(self.db_path, intake_token="demo-secret")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = "http://127.0.0.1:%s" % self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def message(self, **overrides):
        result = {
            "received_at": "2026-10-12T08:30:00",
            "received_at_raw": "2026-10-12 08:30",
            "source": "email",
            "sender": "Ari Example <ari@example.com>",
            "message": "I was charged twice on my annual plan and need a refund.",
            "team": "Billing",
            "topic": "payment",
            "urgency": "High",
            "language": "English",
            "rationale": "Payment failed.",
            "status": "Nouveau",
        }
        result.update(overrides)
        return result

    def test_intake_requires_configured_token_and_persists_message(self):
        payload = {"messages": [self.message()]}
        status, body = request_json(self.base_url + "/api/intake", "POST", payload)
        self.assertEqual(status, 401)

        status, body = request_json(
            self.base_url + "/api/intake", "POST", payload, token="demo-secret"
        )
        self.assertEqual(status, 201)
        self.assertEqual(body["count"], 1)

        status, listing = request_json(self.base_url + "/api/messages?team=Billing")
        self.assertEqual(status, 200)
        self.assertEqual(len(listing["messages"]), 1)
        self.assertEqual(listing["messages"][0]["sender"], "Ari Example <ari@example.com>")

    def test_intake_works_without_n8n_token_configuration(self):
        self.server.intake_token = None
        status, body = request_json(
            self.base_url + "/api/intake", "POST", {"messages": [self.message()]}
        )
        self.assertEqual(status, 201)
        self.assertEqual(body["count"], 1)

    def test_filters_update_assignment_and_status_persist(self):
        first_id = db.insert_message(self.message())
        db.insert_message(self.message(team="Tech", status="En cours"))

        status, listing = request_json(
            self.base_url + "/api/messages?team=Billing&status=Nouveau"
        )
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in listing["messages"]], [first_id])

        status, updated = request_json(
            self.base_url + "/api/messages/%s" % first_id,
            "PATCH",
            {"assignee": "Alex", "status": "En cours"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["message"]["assignee"], "Alex")

        db.init_db(self.db_path)
        stored = db.list_messages(team="Billing", status="En cours")
        self.assertEqual(stored[0]["assignee"], "Alex")

    def test_intake_imports_and_classifies_the_provided_csv(self):
        csv_path = Path(__file__).resolve().parents[1] / "data" / "requests-backlog.csv"
        status, result = request_json(
            self.base_url + "/api/intake",
            "POST",
            {"csv": csv_path.read_text(encoding="utf-8")},
            token="demo-secret",
        )
        self.assertEqual(status, 201)
        self.assertEqual(result["count"], 30)
        self.assertEqual(result["alerts"], 7)

        status, listing = request_json(self.base_url + "/api/messages?urgency=Critical")
        self.assertEqual(status, 200)
        self.assertEqual(len(listing["messages"]), 7)
        stripe = [item for item in listing["messages"] if item["related_group"] == "incident:stripe-checkout"]
        self.assertEqual(len(stripe), 4)


if __name__ == "__main__":
    unittest.main()
