"""Tiny local state store for the uploader: which files have already been sent.

Deliberately separate from db.py's schema — the gaming PC running the
uploader has no need for the full drivers/results schema, just a record of
what it's already pushed to the remote server.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS uploaded_files (
    source_file TEXT PRIMARY KEY,
    uploaded_at TEXT NOT NULL
);
"""


@contextmanager
def connect(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def already_uploaded(conn, source_file: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM uploaded_files WHERE source_file = ?", (source_file,)
    ).fetchone()
    return row is not None


def mark_uploaded(conn, source_file: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO uploaded_files (source_file, uploaded_at) VALUES (?, ?)",
        (source_file, datetime.now(timezone.utc).isoformat()),
    )
