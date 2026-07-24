"""Configuration for the championship tracker.

Reads overrides from config.json in the project root if present; otherwise
uses the defaults below. All settings can be changed without touching code.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.json"

DEFAULTS = {
    # Root "data" directory produced by Pits-n-Giggles (contains <date>/race-info/*.json)
    "watch_dir": str(Path.home() / "pits-n-giggles" / "data"),
    "db_path": str(PROJECT_ROOT / "championship.db"),
    "poll_interval_seconds": 10,
    # Standard F1 points, used only when a race's own points are all zero
    # (i.e. the lobby had the in-game points setting turned off).
    "points_scale": {
        "1": 25, "2": 18, "3": 15, "4": 12, "5": 10,
        "6": 8, "7": 6, "8": 4, "9": 2, "10": 1,
    },
    "fastest_lap_bonus": True,
    "fastest_lap_bonus_requires_top10": True,
    "fastest_lap_bonus_points": 1,
    "web_host": "127.0.0.1",
    "web_port": 5000,
    # Required to access /admin once this is exposed beyond your own machine.
    # Leave admin_password blank to keep the admin panel local-only (disabled).
    "admin_username": "admin",
    "admin_password": "",
    # Set to False on a server deployment that has no local Pits-n-Giggles
    # data folder to watch — races arrive via POST /api/ingest instead.
    "run_watcher": True,
    # Shared secret required on POST /api/ingest (see uploader.py). Leave
    # blank to keep the upload endpoint disabled (404).
    "upload_token": "",
}


def load_config() -> dict:
    config = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            overrides = json.load(f)
        config.update(overrides)
    # Normalize points_scale keys to int
    config["points_scale"] = {int(k): v for k, v in config["points_scale"].items()}
    return config
