"""Entry point for the machine that actually runs Pits n' Giggles.

Watches your local Pits n' Giggles data folder and uploads new race results
to a remotely-hosted championship dashboard (see run.py for the dashboard
itself, which can run on a different machine — e.g. a VPS).

Usage:
    python run_uploader.py

Configure watch_dir, remote_url, and upload_token in uploader_config.json
(see uploader_config.json.example). upload_token must match the dashboard's
upload_token in its own config.json.
"""

import logging

from championship_tracker.uploader import run_forever
from championship_tracker.uploader_config import load_uploader_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


if __name__ == "__main__":
    run_forever(load_uploader_config())
