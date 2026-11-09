"""Persist a one-time intent before an external action could take place.

This example has no network transport. An unresolved intent must be reconciled
against independent evidence after restart. A terminal receipt is opaque here:
the caller must have verified it before recording its identifier.
"""

import sqlite3
from pathlib import Path


def _require_text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("a non-blank string is required")


class IntentJournal:
    def __init__(self, path: Path):
        self._db = sqlite3.connect(path)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS intents (
                intent_id TEXT PRIMARY KEY NOT NULL,
                payload TEXT NOT NULL,
                terminal_receipt TEXT UNIQUE
            )
        """)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._db.close()

    def claim(self, intent_id: str, payload: str) -> bool:
        """Exactly one caller receives True for a given immutable intent."""
        _require_text(intent_id)
        _require_text(payload)
        with self._db:
            cursor = self._db.execute("""
                INSERT INTO intents(intent_id, payload) VALUES (?, ?)
                ON CONFLICT(intent_id) DO NOTHING
            """, (intent_id, payload))
            if cursor.rowcount == 1:
                return True
            stored, = self._db.execute(
                "SELECT payload FROM intents WHERE intent_id = ?", (intent_id,)
            ).fetchone()
            if stored != payload:
                raise ValueError("an existing intent has a different payload")
            return False

    def unresolved(self) -> tuple[str, ...]:
        rows = self._db.execute(
            "SELECT intent_id FROM intents WHERE terminal_receipt IS NULL ORDER BY intent_id"
        )
        return tuple(row[0] for row in rows)

    def confirm(self, intent_id: str, receipt: str) -> None:
        """Bind a verified terminal receipt. Identical replay leaves state intact."""
        _require_text(intent_id)
        _require_text(receipt)
        with self._db:
            cursor = self._db.execute("""
                UPDATE intents SET terminal_receipt = ? WHERE intent_id = ?
                    AND (terminal_receipt IS NULL OR terminal_receipt = ?)
            """, (receipt, intent_id, receipt))
            if cursor.rowcount != 1:
                raise ValueError("unknown intent or conflicting receipt")
