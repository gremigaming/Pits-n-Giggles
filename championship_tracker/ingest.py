"""Parse a Pits-n-Giggles saved race JSON and import it into the database."""

import json
import logging
from pathlib import Path
from typing import Optional

from . import db

logger = logging.getLogger(__name__)


def _compute_points(entries: list[dict], points_scale: dict[int, int]) -> dict[int, int]:
    """Points per driver index, keyed by classification-data index.

    Uses the game's own final-classification points if any are non-zero
    (the lobby had the points setting on). Otherwise falls back to our own
    standard scale based on finishing position.
    """
    raw_points = {
        entry["index"]: entry["final-classification"]["points"] for entry in entries
    }
    if any(p > 0 for p in raw_points.values()):
        return raw_points

    computed = {}
    for entry in entries:
        position = entry["final-classification"]["position"]
        computed[entry["index"]] = points_scale.get(position, 0)
    return computed


def _fastest_lap_driver_index(race_json: dict) -> Optional[int]:
    fastest = race_json.get("records", {}).get("fastest", {}).get("lap")
    if not fastest:
        return None
    return fastest.get("driver-index")


def parse_race_json(race_json: dict, config: dict, source_label: str) -> dict:
    """Parse an already-loaded race JSON payload into a dict ready for db import.

    `source_label` is stored for reference only (a file path for locally
    ingested races, or the original filename for races received over the
    upload API) — it plays no role in dedup, which is keyed on session_uid.

    Returns a dict with race metadata and a list of per-driver result rows.
    """
    session_info = race_json["session-info"]
    debug_info = race_json["debug"]
    entries = race_json["classification-data"]

    points_by_index = _compute_points(entries, config["points_scale"])
    fastest_lap_index = _fastest_lap_driver_index(race_json)

    results = []
    for entry in entries:
        fc = entry["final-classification"]
        index = entry["index"]

        is_fastest_lap = index == fastest_lap_index
        bonus_points = 0
        if (
            is_fastest_lap
            and config["fastest_lap_bonus"]
            and (
                not config["fastest_lap_bonus_requires_top10"]
                or fc["position"] <= 10
            )
            and fc["result-status"] == "FINISHED"
        ):
            bonus_points = config["fastest_lap_bonus_points"]

        results.append({
            "alias": entry["driver-name"],
            "team_id": entry.get("participant-data", {}).get("team-id"),
            "position": fc["position"],
            "grid_position": fc["grid-position"],
            "points": points_by_index[index],
            "bonus_points": bonus_points,
            "result_status": fc["result-status"],
            "best_lap_time_ms": fc["best-lap-time-ms"],
            "total_race_time_s": fc["total-race-time"],
            "num_pit_stops": fc["num-pit-stops"],
            "penalties_time": fc["penalties-time"],
            "is_fastest_lap": is_fastest_lap,
        })

    return {
        "session_uid": str(debug_info["session-uid"]),
        "track": session_info.get("track-id"),
        "session_type": session_info.get("session-type"),
        "formula": session_info.get("formula"),
        "total_laps": session_info.get("total-laps"),
        "race_timestamp": debug_info.get("timestamp"),
        "source_file": source_label,
        "results": results,
    }


def parse_race_file(path: Path, config: dict) -> dict:
    """Parse a saved race JSON file from disk into a dict ready for db import."""
    with open(path, "r", encoding="utf-8") as f:
        race_json = json.load(f)
    return parse_race_json(race_json, config, str(path))


def import_race(conn, race: dict) -> bool:
    """Insert a parsed race and its results. Returns False if already imported."""
    from datetime import datetime, timezone

    if db.race_already_imported(conn, race["session_uid"]):
        logger.info("Race %s already imported, skipping", race["session_uid"])
        return False

    conn.execute(
        """
        INSERT INTO races (session_uid, track, session_type, formula, total_laps,
                            race_timestamp, source_file, imported_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            race["session_uid"], race["track"], race["session_type"], race["formula"],
            race["total_laps"], race["race_timestamp"], race["source_file"],
            datetime.now(timezone.utc).isoformat(),
        ),
    )

    for result in race["results"]:
        driver_id, _needs_review = db.resolve_driver_id(conn, result["alias"])
        conn.execute(
            """
            INSERT INTO results (session_uid, driver_id, alias_used, position, grid_position,
                                  points, bonus_points, result_status, best_lap_time_ms,
                                  total_race_time_s, num_pit_stops, penalties_time, team_id,
                                  is_fastest_lap)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                race["session_uid"], driver_id, result["alias"], result["position"],
                result["grid_position"], result["points"], result["bonus_points"],
                result["result_status"], result["best_lap_time_ms"],
                result["total_race_time_s"], result["num_pit_stops"],
                result["penalties_time"], result["team_id"], int(result["is_fastest_lap"]),
            ),
        )

    logger.info("Imported race %s (%s) with %d drivers",
                race["session_uid"], race["track"], len(race["results"]))
    return True


def ingest_file(db_path: str, path: Path, config: dict) -> bool:
    race = parse_race_file(path, config)
    with db.connect(db_path) as conn:
        return import_race(conn, race)
