from pathlib import Path

import pytest

from championship_tracker import db
from championship_tracker.config import DEFAULTS
from championship_tracker.ingest import import_race, parse_race_file

FIXTURE = Path(__file__).parent / "fixtures" / "sample_race.json"


@pytest.fixture
def config():
    cfg = dict(DEFAULTS)
    cfg["points_scale"] = {int(k): v for k, v in DEFAULTS["points_scale"].items()}
    return cfg


def test_parse_race_file_uses_game_points_when_present(config):
    race = parse_race_file(FIXTURE, config)

    assert race["session_uid"] == "1086206222430817135"
    assert race["track"] == "Abu Dhabi"
    assert len(race["results"]) == 10

    by_alias = {r["alias"]: r for r in race["results"]}
    assert by_alias["Dmitriy_Glinnik"]["position"] == 1
    assert by_alias["Dmitriy_Glinnik"]["points"] == 25
    assert by_alias["TTV/GreMi_Gaming"]["points"] == 15
    assert by_alias["JSA_428"]["result_status"] == "DID_NOT_FINISH"
    assert by_alias["JSA_428"]["points"] == 0


def test_fastest_lap_bonus_awarded_to_correct_driver(config):
    race = parse_race_file(FIXTURE, config)
    by_alias = {r["alias"]: r for r in race["results"]}

    # DDRK set the fastest lap in the fixture, finishing P8.
    assert by_alias["DDRK"]["is_fastest_lap"] is True
    assert by_alias["DDRK"]["bonus_points"] == 1
    assert by_alias["Dmitriy_Glinnik"]["is_fastest_lap"] is False
    assert by_alias["Dmitriy_Glinnik"]["bonus_points"] == 0


def test_fastest_lap_bonus_disabled_via_config(config):
    config["fastest_lap_bonus"] = False
    race = parse_race_file(FIXTURE, config)
    by_alias = {r["alias"]: r for r in race["results"]}
    assert by_alias["DDRK"]["bonus_points"] == 0


def test_points_fallback_to_standard_scale_when_all_zero(config):
    race = parse_race_file(FIXTURE, config)
    for r in race["results"]:
        r["points"] = 0  # simulate a lobby with the points setting off

    # Re-derive via the same helper used internally to confirm the fallback math.
    from championship_tracker.ingest import _compute_points
    import json

    with open(FIXTURE) as f:
        race_json = json.load(f)
    for entry in race_json["classification-data"]:
        entry["final-classification"]["points"] = 0

    points_by_index = _compute_points(race_json["classification-data"], config["points_scale"])
    assert points_by_index[
        next(e["index"] for e in race_json["classification-data"] if e["driver-name"] == "Dmitriy_Glinnik")
    ] == 25


def test_anonymized_alias_flagged_as_needs_review(tmp_path, config):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    race = parse_race_file(FIXTURE, config)

    with db.connect(db_path) as conn:
        import_race(conn, race)
        placeholder = conn.execute(
            "SELECT * FROM drivers WHERE display_name LIKE '%221 #45%'"
        ).fetchone()
        assert placeholder is not None
        assert placeholder["needs_review"] == 1

        normal = conn.execute(
            "SELECT * FROM drivers WHERE display_name = 'Dmitriy_Glinnik'"
        ).fetchone()
        assert normal is not None
        assert normal["needs_review"] == 0


def test_reimporting_same_race_is_a_noop(tmp_path, config):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    race = parse_race_file(FIXTURE, config)

    with db.connect(db_path) as conn:
        first = import_race(conn, race)
        second = import_race(conn, race)

    assert first is True
    assert second is False

    with db.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM results").fetchone()["c"]
    assert count == 10


def test_same_alias_reused_across_races_maps_to_same_driver(tmp_path, config):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        first_id, _ = db.resolve_driver_id(conn, "Dmitriy_Glinnik")
        second_id, _ = db.resolve_driver_id(conn, "Dmitriy_Glinnik")
    assert first_id == second_id


def test_anonymized_placeholder_never_auto_merged_across_races(tmp_path, config):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        first_id, first_review = db.resolve_driver_id(conn, "221 #45")
        second_id, second_review = db.resolve_driver_id(conn, "221 #45")

    assert first_review is True
    assert second_review is True
    assert first_id != second_id
