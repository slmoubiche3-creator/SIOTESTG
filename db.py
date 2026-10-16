"""SQLite storage for the request-triage demo."""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


_DATABASE_PATH = None


def init_db(path):
    """Select the database file and create the schema if needed."""
    global _DATABASE_PATH
    _DATABASE_PATH = str(path)
    Path(_DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT,
                received_at_raw TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'unknown',
                sender TEXT NOT NULL DEFAULT 'Unknown sender',
                message TEXT NOT NULL,
                team TEXT NOT NULL DEFAULT 'Support',
                topic TEXT NOT NULL DEFAULT 'Other',
                urgency TEXT NOT NULL DEFAULT 'Normal',
                language TEXT NOT NULL DEFAULT 'Unknown',
                rationale TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Nouveau',
                assignee TEXT NOT NULL DEFAULT '',
                needs_review INTEGER NOT NULL DEFAULT 0,
                review_flags TEXT NOT NULL DEFAULT '[]',
                is_spam INTEGER NOT NULL DEFAULT 0,
                sender_warning TEXT NOT NULL DEFAULT '',
                related_group TEXT NOT NULL DEFAULT '',
                alert_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_team_status
                ON messages(team, status);
            CREATE INDEX IF NOT EXISTS idx_messages_urgency
                ON messages(urgency);
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0
            );
            """
        )


def _connect():
    if _DATABASE_PATH is None:
        raise RuntimeError("Database is not initialized; call init_db(path) first")
    connection = sqlite3.connect(_DATABASE_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _row_to_message(row):
    if row is None:
        return None
    item = dict(row)
    item["needs_review"] = bool(item["needs_review"])
    item["is_spam"] = bool(item["is_spam"])
    try:
        item["review_flags"] = json.loads(item["review_flags"] or "[]")
    except (TypeError, ValueError):
        item["review_flags"] = []
    return item


def insert_message(message):
    """Insert a message and, when critical, persist its alert in the same transaction."""
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    values = {
        "received_at": message.get("received_at"),
        "received_at_raw": message.get("received_at_raw", ""),
        "source": message.get("source") or "unknown",
        "sender": message.get("sender") or "Unknown sender",
        "message": message.get("message") or "",
        "team": message.get("team") or "Support",
        "topic": message.get("topic") or "Other",
        "urgency": message.get("urgency") or "Normal",
        "language": message.get("language") or "Unknown",
        "rationale": message.get("rationale") or "",
        "status": message.get("status") or "Nouveau",
        "assignee": message.get("assignee") or "",
        "needs_review": int(bool(message.get("needs_review", False))),
        "review_flags": json.dumps(message.get("review_flags") or [], ensure_ascii=False),
        "is_spam": int(bool(message.get("is_spam", False))),
        "sender_warning": message.get("sender_warning") or "",
        "related_group": message.get("related_group") or "",
        "alert_reason": message.get("alert_reason") or "",
        "created_at": now,
    }
    if not values["message"]:
        raise ValueError("message is required")

    with _connect() as connection:
        cursor = connection.execute(
            """INSERT INTO messages (
                received_at, received_at_raw, source, sender, message, team, topic,
                urgency, language, rationale, status, assignee, needs_review,
                review_flags, is_spam, sender_warning, related_group, alert_reason,
                created_at
            ) VALUES (
                :received_at, :received_at_raw, :source, :sender, :message, :team,
                :topic, :urgency, :language, :rationale, :status, :assignee,
                :needs_review, :review_flags, :is_spam, :sender_warning,
                :related_group, :alert_reason, :created_at
            )""",
            values,
        )
        message_id = cursor.lastrowid
        if values["urgency"] == "Critical":
            reason = values["alert_reason"] or values["rationale"] or "Critical request"
            connection.execute(
                "INSERT INTO alerts (message_id, reason, created_at) VALUES (?, ?, ?)",
                (message_id, reason, now),
            )
        return message_id


def list_messages(team=None, status=None, urgency=None, needs_review=None, query=None):
    clauses = []
    parameters = []
    for column, value in (("team", team), ("status", status), ("urgency", urgency)):
        if value:
            clauses.append(column + " = ?")
            parameters.append(value)
    if needs_review is not None:
        clauses.append("needs_review = ?")
        parameters.append(int(bool(needs_review)))
    if query:
        clauses.append("(message LIKE ? OR sender LIKE ? OR topic LIKE ?)")
        needle = "%" + query.replace("%", "\\%").replace("_", "\\_") + "%"
        parameters.extend((needle, needle, needle))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM messages" + where +
            " ORDER BY CASE urgency WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 "
            "WHEN 'Normal' THEN 2 ELSE 3 END, received_at DESC, id DESC",
            parameters,
        ).fetchall()
    return [_row_to_message(row) for row in rows]


def update_message(message_id, updates):
    allowed = {"assignee", "status"}
    if not updates or not set(updates).issubset(allowed):
        raise ValueError("Only assignee and status can be updated")
    assignments = ", ".join(column + " = ?" for column in updates)
    values = list(updates.values()) + [message_id]
    with _connect() as connection:
        connection.execute(
            "UPDATE messages SET " + assignments + " WHERE id = ?", values
        )
        row = connection.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    return _row_to_message(row)


def get_summary():
    with _connect() as connection:
        counts = connection.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN urgency = 'Critical' THEN 1 ELSE 0 END) AS critical,
                      SUM(CASE WHEN needs_review = 1 THEN 1 ELSE 0 END) AS needs_review
               FROM messages"""
        ).fetchone()
        alert_rows = connection.execute(
            """SELECT alerts.id, alerts.message_id, alerts.reason, alerts.created_at,
                      alerts.acknowledged, messages.team, messages.message
               FROM alerts JOIN messages ON messages.id = alerts.message_id
               ORDER BY alerts.created_at DESC, alerts.id DESC"""
        ).fetchall()
        groups = connection.execute(
            """SELECT related_group, COUNT(*) AS count,
                      MIN(message) AS sample_message,
                      GROUP_CONCAT(id) AS message_ids
               FROM messages WHERE related_group != ''
               GROUP BY related_group HAVING COUNT(*) > 1
               ORDER BY count DESC"""
        ).fetchall()
    return {
        "total": counts["total"] or 0,
        "critical": counts["critical"] or 0,
        "needs_review": counts["needs_review"] or 0,
        "alerts": [dict(row) for row in alert_rows],
        "related_groups": [dict(row) for row in groups],
    }
