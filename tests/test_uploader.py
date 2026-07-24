import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from championship_tracker import uploader_state as state
from championship_tracker.uploader import scan_once

FIXTURE = Path(__file__).parent / "fixtures" / "sample_race.json"


def make_config(tmp_path):
    watch_dir = tmp_path / "data"
    (watch_dir / "2026_07_15" / "race-info").mkdir(parents=True)
    shutil.copy(FIXTURE, watch_dir / "2026_07_15" / "race-info" / "sample_race.json")

    config = {
        "watch_dir": str(watch_dir),
        "remote_url": "https://example.test/api/ingest",
        "upload_token": "secret-token",
        "state_db_path": str(tmp_path / "uploaded_state.db"),
        "poll_interval_seconds": 10,
    }
    state.init_db(config["state_db_path"])
    return config


def _ok_response():
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"imported": True}
    return resp


def test_scan_once_uploads_new_files_with_token_header(tmp_path):
    config = make_config(tmp_path)

    with patch("championship_tracker.uploader.requests.post", return_value=_ok_response()) as mock_post:
        uploaded = scan_once(config)

    assert uploaded == 1
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["X-Upload-Token"] == "secret-token"


def test_scan_once_does_not_reupload_already_sent_files(tmp_path):
    config = make_config(tmp_path)

    with patch("championship_tracker.uploader.requests.post", return_value=_ok_response()) as mock_post:
        scan_once(config)
        uploaded_again = scan_once(config)

    assert uploaded_again == 0
    assert mock_post.call_count == 1


def test_scan_once_retries_on_failed_upload(tmp_path):
    config = make_config(tmp_path)

    with patch("championship_tracker.uploader.requests.post", side_effect=Exception("network error")):
        uploaded = scan_once(config)
    assert uploaded == 0

    # Not marked as uploaded, so a later successful scan should still send it.
    with patch("championship_tracker.uploader.requests.post", return_value=_ok_response()) as mock_post:
        uploaded = scan_once(config)
    assert uploaded == 1
    mock_post.assert_called_once()
