"""Watches the local Pits-n-Giggles data directory and uploads new race JSON
files to a remote championship tracker's /api/ingest endpoint.

Runs on the machine that actually has Pits n' Giggles installed (typically
the gaming PC), separately from the dashboard itself (see watcher.py, which
does the equivalent job for a locally-hosted dashboard).
"""

import json
import logging
import time
from pathlib import Path

import requests

from . import uploader_state as state

logger = logging.getLogger(__name__)


def scan_once(config: dict) -> int:
    """Upload any not-yet-sent race JSON files. Returns count uploaded."""
    watch_dir = Path(config["watch_dir"])
    if not watch_dir.exists():
        logger.warning("Watch directory %s does not exist yet", watch_dir)
        return 0

    candidate_files = sorted(watch_dir.glob("*/race-info/*.json"))

    with state.connect(config["state_db_path"]) as conn:
        new_files = [
            f for f in candidate_files if not state.already_uploaded(conn, str(f))
        ]

    uploaded = 0
    for path in new_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                race_json = json.load(f)

            response = requests.post(
                config["remote_url"],
                json=race_json,
                headers={"X-Upload-Token": config["upload_token"]},
                timeout=30,
            )
            response.raise_for_status()

            with state.connect(config["state_db_path"]) as conn:
                state.mark_uploaded(conn, str(path))
            uploaded += 1
            logger.info("Uploaded %s -> %s", path, response.json())
        except Exception:
            logger.exception("Failed to upload %s, will retry next scan", path)

    return uploaded


def run_forever(config: dict) -> None:
    """Blocking loop: scan on startup, then poll at the configured interval."""
    state.init_db(config["state_db_path"])
    logger.info("Watching %s, uploading to %s", config["watch_dir"], config["remote_url"])
    while True:
        uploaded = scan_once(config)
        if uploaded:
            logger.info("Uploaded %d new race(s)", uploaded)
        time.sleep(config["poll_interval_seconds"])
