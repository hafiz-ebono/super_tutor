"""
Session lifecycle status tracking for background workflow tasks.

Lightweight SQLite store separate from agno's session data.
Tracks the full lifecycle: pending → complete | failed

Deliberately simple — no ORM, no abstraction layers.
Can be swapped for Redis/Postgres without changing the interface.
"""
import logging
import os
import sqlite3
from datetime import datetime, timezone

from app.config import get_settings

logger = logging.getLogger("super_tutor.session_status")


def _db_path() -> str:
    return get_settings().status_db_path


def _get_conn(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    # WAL mode: readers and writers can proceed concurrently without blocking each other.
    conn.execute("PRAGMA journal_mode=WAL")
    # busy_timeout: retry for up to 5 s before raising OperationalError on lock contention.
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_status (
            session_id   TEXT PRIMARY KEY,
            status       TEXT NOT NULL DEFAULT 'pending',
            error_kind   TEXT,
            error_message TEXT,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        )
    """)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session_status(session_id: str) -> None:
    """Insert a new session with status=pending. Idempotent (INSERT OR IGNORE)."""
    path = _db_path()
    ts = _now()
    with _get_conn(path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO session_status"
            " (session_id, status, created_at, updated_at) VALUES (?, 'pending', ?, ?)",
            (session_id, ts, ts),
        )
    logger.debug("Status created — session_id=%s status=pending", session_id)


def update_session_status(
    session_id: str,
    status: str,
    error_kind: str = "",
    error_message: str = "",
) -> None:
    """Update status to 'complete' or 'failed' with optional error details."""
    path = _db_path()
    with _get_conn(path) as conn:
        conn.execute(
            "UPDATE session_status"
            " SET status=?, error_kind=?, error_message=?, updated_at=?"
            " WHERE session_id=?",
            (status, error_kind or None, error_message or None, _now(), session_id),
        )
    logger.debug(
        "Status updated — session_id=%s status=%s error_kind=%s",
        session_id, status, error_kind or "-",
    )


def mark_stale_sessions_failed(stale_after_seconds: int = 3700) -> int:
    """
    Mark any session that has been 'pending' for longer than stale_after_seconds as 'failed'.
    Called at app startup to clean up sessions orphaned by a previous crash.
    Returns the number of sessions updated.
    """
    path = _db_path()
    if not os.path.exists(path):
        return 0
    cutoff = datetime.now(timezone.utc).timestamp() - stale_after_seconds
    with _get_conn(path) as conn:
        cursor = conn.execute(
            "UPDATE session_status SET status='failed', error_kind='timeout',"
            " error_message='Session timed out — server may have restarted.', updated_at=?"
            " WHERE status='pending' AND created_at < ?",
            (_now(), datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()),
        )
        count = cursor.rowcount
    if count:
        logger.warning("Startup cleanup: marked %d stale pending session(s) as failed", count)
    return count


def get_session_status(session_id: str) -> dict | None:
    """
    Return status dict for session_id, or None if not found.
    Shape: { "status": str, "error_kind": str, "error_message": str }
    """
    path = _db_path()
    if not os.path.exists(path):
        return None
    with _get_conn(path) as conn:
        row = conn.execute(
            "SELECT status, error_kind, error_message"
            " FROM session_status WHERE session_id=?",
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "status": row[0],
        "error_kind": row[1] or "",
        "error_message": row[2] or "",
    }
