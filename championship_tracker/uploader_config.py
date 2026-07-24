"""Configuration for the uploader — runs on the machine that has Pits n'
Giggles installed and pushes new race JSON files to a remote dashboard.

Separate from config.py (the dashboard's config): the two processes
typically run on different machines with no shared config.json.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOADER_CONFIG_FILE = PROJECT_ROOT / "uploader_config.json"

UPLOADER_DEFAULTS = {
    # Root "data" directory produced by Pits-n-Giggles (contains <date>/race-info/*.json)
    "watch_dir": str(Path.home() / "pits-n-giggles" / "data"),
    "remote_url": "https://your-dashboard-domain.example.com/api/ingest",
    "upload_token": "",
    "state_db_path": str(PROJECT_ROOT / "uploaded_state.db"),
    "poll_interval_seconds": 10,
}


def load_uploader_config() -> dict:
    config = dict(UPLOADER_DEFAULTS)
    if UPLOADER_CONFIG_FILE.exists():
        with open(UPLOADER_CONFIG_FILE, "r", encoding="utf-8") as f:
            overrides = json.load(f)
        config.update(overrides)
    return config
