"""SQLite storage for consent, webhook dedupe and interaction logs (Phase 1).

Moves to Postgres in Phase 2. User ids are stored as salted hashes only.
"""

import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.models import InteractionRecord

Consent = Literal["unknown", "pending", "yes", "no"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_hash TEXT PRIMARY KEY,
    consent TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS processed_messages (
    key TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    channel TEXT NOT NULL,
    user_hash TEXT NOT NULL,
    kind TEXT NOT NULL,
    consented INTEGER NOT NULL,
    question TEXT,
    search_query TEXT,
    diagnosis TEXT,
    retrieved_ids TEXT,
    answer TEXT,
    confidence TEXT,
    fallback_reason TEXT,
    model TEXT
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, db_path: Path | str, salt: str):
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.executescript(SCHEMA)
        self._salt = salt

    def user_hash(self, channel: str, user_id: str) -> str:
        return hashlib.sha256(f"{self._salt}:{channel}:{user_id}".encode()).hexdigest()[:32]

    def get_consent(self, user_hash: str) -> Consent:
        row = self._db.execute(
            "SELECT consent FROM users WHERE user_hash = ?", (user_hash,)
        ).fetchone()
        return row[0] if row else "unknown"

    def set_consent(self, user_hash: str, consent: Consent) -> None:
        self._db.execute(
            "INSERT INTO users (user_hash, consent, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_hash) DO UPDATE SET consent = excluded.consent",
            (user_hash, consent, _now()),
        )
        self._db.commit()

    def mark_processed(self, channel: str, message_id: str) -> bool:
        """Return True the first time a message is seen, False for duplicates."""
        try:
            self._db.execute(
                "INSERT INTO processed_messages (key, created_at) VALUES (?, ?)",
                (f"{channel}:{message_id}", _now()),
            )
            self._db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def log_interaction(self, record: InteractionRecord) -> None:
        consented = self.get_consent(record.user_hash) == "yes"
        data = asdict(record)
        if not consented:
            for key in ("question", "search_query", "answer"):
                data[key] = ""
            data["diagnosis"] = None
        self._db.execute(
            "INSERT INTO interactions (created_at, channel, user_hash, kind, consented, question, "
            "search_query, diagnosis, retrieved_ids, answer, confidence, fallback_reason, model) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _now(),
                data["channel"],
                data["user_hash"],
                data["kind"],
                int(consented),
                data["question"],
                data["search_query"],
                json.dumps(data["diagnosis"]) if data["diagnosis"] else None,
                json.dumps(data["retrieved_ids"]),
                data["answer"],
                data["confidence"],
                data["fallback_reason"],
                data["model"],
            ),
        )
        self._db.commit()

    def interactions(self) -> list[dict]:
        cur = self._db.execute("SELECT * FROM interactions ORDER BY id")
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
