"""SQLite persistence for races, drivers, aliases, and results."""

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

# Anonymized placeholder names PnG generates when a driver's broadcast
# settings hide their real name, e.g. "221 #45" (team-id + race-number).
# These are NOT stable identities across races and must never be auto-merged.
UNIDENTIFIED_ALIAS_RE = re.compile(r"^\d+\s*#\d+$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS races (
    session_uid TEXT PRIMARY KEY,
    track TEXT,
    session_type TEXT,
    formula TEXT,
    total_laps INTEGER,
    race_timestamp TEXT,
    source_file TEXT,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,
    needs_review INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS driver_aliases (
    alias TEXT PRIMARY KEY,
    driver_id INTEGER NOT NULL REFERENCES drivers(id)
);

CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_uid TEXT NOT NULL REFERENCES races(session_uid),
    driver_id INTEGER NOT NULL REFERENCES drivers(id),
    alias_used TEXT NOT NULL,
    position INTEGER,
    grid_position INTEGER,
    points INTEGER NOT NULL DEFAULT 0,
    bonus_points INTEGER NOT NULL DEFAULT 0,
    result_status TEXT,
    best_lap_time_ms INTEGER,
    total_race_time_s REAL,
    num_pit_stops INTEGER,
    penalties_time INTEGER,
    team_id TEXT,
    is_fastest_lap INTEGER NOT NULL DEFAULT 0,
    UNIQUE(session_uid, driver_id)
);
"""


@contextmanager
def connect(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def race_already_imported(conn, session_uid: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM races WHERE session_uid = ?", (session_uid,)
    ).fetchone()
    return row is not None


def known_source_files(conn) -> set[str]:
    """All file paths already recorded in the races table.

    Used by the watcher to skip re-parsing files it has already imported,
    without needing a separate processed-files table.
    """
    rows = conn.execute("SELECT source_file FROM races").fetchall()
    return {row["source_file"] for row in rows}


def resolve_driver_id(conn, alias: str) -> tuple[int, bool]:
    """Return (driver_id, needs_review) for a race-entry alias.

    Identified aliases are matched/created by exact name and reused across
    races. Anonymized placeholder aliases (see UNIDENTIFIED_ALIAS_RE) always
    get a fresh driver record, since the same placeholder string can refer to
    a different real person in a different race.
    """
    is_placeholder = bool(UNIDENTIFIED_ALIAS_RE.match(alias))
    now = datetime.now(timezone.utc).isoformat()

    if not is_placeholder:
        row = conn.execute(
            "SELECT driver_id FROM driver_aliases WHERE alias = ?", (alias,)
        ).fetchone()
        if row:
            return row["driver_id"], False

    display_name = f"Unidentified ({alias})" if is_placeholder else alias
    cur = conn.execute(
        "INSERT INTO drivers (display_name, needs_review, created_at) VALUES (?, ?, ?)",
        (display_name, int(is_placeholder), now),
    )
    driver_id = cur.lastrowid

    if not is_placeholder:
        conn.execute(
            "INSERT INTO driver_aliases (alias, driver_id) VALUES (?, ?)",
            (alias, driver_id),
        )

    return driver_id, is_placeholder


def merge_driver(conn, from_driver_id: int, into_driver_id: int) -> None:
    """Merge one driver record's results/aliases into another, then delete it.

    If both drivers already have a result in the same race (only possible if
    they were mis-merged), the target driver's row wins and the source row is
    dropped, rather than violating the one-result-per-driver-per-race constraint.
    """
    rows = conn.execute(
        "SELECT session_uid FROM results WHERE driver_id = ?", (from_driver_id,)
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            UPDATE results SET driver_id = ?
            WHERE driver_id = ? AND session_uid = ?
            AND NOT EXISTS (
                SELECT 1 FROM results WHERE driver_id = ? AND session_uid = ?
            )
            """,
            (into_driver_id, from_driver_id, row["session_uid"], into_driver_id, row["session_uid"]),
        )
    conn.execute("DELETE FROM results WHERE driver_id = ?", (from_driver_id,))
    conn.execute(
        "UPDATE driver_aliases SET driver_id = ? WHERE driver_id = ?",
        (into_driver_id, from_driver_id),
    )
    conn.execute("DELETE FROM drivers WHERE id = ?", (from_driver_id,))


def rename_driver(conn, driver_id: int, new_name: str) -> None:
    conn.execute(
        "UPDATE drivers SET display_name = ?, needs_review = 0 WHERE id = ?",
        (new_name, driver_id),
    )
    conn.execute(
        "INSERT OR IGNORE INTO driver_aliases (alias, driver_id) VALUES (?, ?)",
        (new_name, driver_id),
    )
