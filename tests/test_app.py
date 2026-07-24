import base64

import pytest

from championship_tracker.app import create_app
from championship_tracker.config import DEFAULTS


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
