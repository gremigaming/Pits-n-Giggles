import base64
import json
from pathlib import Path

import pytest

from championship_tracker import db
from championship_tracker.app import create_app
from championship_tracker.config import DEFAULTS

FIXTURE = Path(__file__).parent / "fixtures" / "sample_race.json"


def make_config(tmp_path, **overrides):
    cfg = dict(DEFAULTS)
    cfg["points_scale"] = {int(k): v for k, v in DEFAULTS["points_scale"].items()}
    cfg["db_path"] = str(tmp_path / "test.db")
    cfg.update(overrides)
    return cfg


def basic_auth_header(username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_public_pages_accessible_without_auth(tmp_path):
    app = create_app(make_config(tmp_path, admin_password="secret"))
    client = app.test_client()
    assert client.get("/").status_code == 200
    assert client.get("/races").status_code == 200


def test_admin_disabled_when_no_password_configured(tmp_path):
    app = create_app(make_config(tmp_path, admin_password=""))
    client = app.test_client()
    assert client.get("/admin").status_code == 404


def test_admin_requires_auth_when_password_configured(tmp_path):
    app = create_app(make_config(tmp_path, admin_password="secret"))
    client = app.test_client()

    resp = client.get("/admin")
    assert resp.status_code == 401

    resp = client.get("/admin", headers=basic_auth_header("admin", "wrong"))
    assert resp.status_code == 401

    resp = client.get("/admin", headers=basic_auth_header("admin", "secret"))
    assert resp.status_code == 200


def test_admin_post_routes_also_require_auth(tmp_path):
    app = create_app(make_config(tmp_path, admin_password="secret"))
    client = app.test_client()

    resp = client.post("/admin/rename", data={"driver_id": "1", "new_name": "x"})
    assert resp.status_code == 401


def test_ingest_disabled_when_no_upload_token_configured(tmp_path):
    app = create_app(make_config(tmp_path, upload_token=""))
    client = app.test_client()
    resp = client.post("/api/ingest", json={"anything": True})
    assert resp.status_code == 404


def test_ingest_requires_matching_token(tmp_path):
    app = create_app(make_config(tmp_path, upload_token="secret-token"))
    client = app.test_client()

    resp = client.post("/api/ingest", json={"anything": True})
    assert resp.status_code == 401

    resp = client.post(
        "/api/ingest", json={"anything": True},
        headers={"X-Upload-Token": "wrong"},
    )
    assert resp.status_code == 401


def test_ingest_imports_valid_race_payload(tmp_path):
    config = make_config(tmp_path, upload_token="secret-token")
    app = create_app(config)
    client = app.test_client()

    with open(FIXTURE) as f:
        race_json = json.load(f)

    resp = client.post(
        "/api/ingest", json=race_json,
        headers={"X-Upload-Token": "secret-token"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["imported"] is True

    with db.connect(config["db_path"]) as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM results").fetchone()["c"]
    assert count == 10

    # Re-uploading the same race is a no-op, not a duplicate/error.
    resp = client.post(
        "/api/ingest", json=race_json,
        headers={"X-Upload-Token": "secret-token"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["imported"] is False


def test_ingest_rejects_malformed_payload(tmp_path):
    app = create_app(make_config(tmp_path, upload_token="secret-token"))
    client = app.test_client()

    resp = client.post(
        "/api/ingest", json={"session-info": {}},
        headers={"X-Upload-Token": "secret-token"},
    )
    assert resp.status_code == 400
