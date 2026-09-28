from __future__ import annotations

import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Punch:
    event_id: str
    device_id: str
    uid: str
    punched_at: str
    created_at: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


class PunchStore:
    def __init__(self, path: str, device_id: str) -> None:
        self.device_id = device_id
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._connection:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS punches (
                    event_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    uid TEXT NOT NULL,
                    punched_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    uploaded_at TEXT
                )
                """
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_punches_pending "
                "ON punches(uploaded_at, punched_at)"
            )

    def add(self, uid: str, when: datetime | None = None) -> Punch:
        when = when or datetime.now().astimezone()
        punch = Punch(
            event_id=str(uuid.uuid4()),
            device_id=self.device_id,
            uid=uid.upper(),
            punched_at=when.isoformat(timespec="seconds"),
            created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO punches(event_id, device_id, uid, punched_at, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (punch.event_id, punch.device_id, punch.uid, punch.punched_at, punch.created_at),
            )
        return punch

    def pending(self, limit: int) -> list[Punch]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT event_id, device_id, uid, punched_at, created_at FROM punches "
                "WHERE uploaded_at IS NULL ORDER BY punched_at, event_id LIMIT ?",
                (limit,),
            ).fetchall()
        return [Punch(**dict(row)) for row in rows]

    def mark_uploaded(self, event_ids: list[str], uploaded_at: str | None = None) -> None:
        if not event_ids:
            return
        uploaded_at = uploaded_at or datetime.now().astimezone().isoformat(timespec="seconds")
        placeholders = ",".join("?" for _ in event_ids)
        with self._lock, self._connection:
            self._connection.execute(
                f"UPDATE punches SET uploaded_at=? WHERE event_id IN ({placeholders})",
                [uploaded_at, *event_ids],
            )

    def count_pending(self) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS count FROM punches WHERE uploaded_at IS NULL"
            ).fetchone()
        return int(row["count"])
