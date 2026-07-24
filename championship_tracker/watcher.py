"""Polls the Pits-n-Giggles data directory for new saved race JSON files."""

import logging
import time
from pathlib import Path

from . import db
from .ingest import ingest_file

logger = logging.getLogger(__name__)


def scan_once(config: dict) -> int:
    """Import any not-yet-seen race JSON files. Returns count imported."""
    watch_dir = Path(config["watch_dir"])
    if not watch_dir.exists():
        logger.warning("Watch directory %s does not exist yet", watch_dir)
        return 0

    candidate_files = sorted(watch_dir.glob("*/race-info/*.json"))

    with db.connect(config["db_path"]) as conn:
        known = db.known_source_files(conn)
    new_files = [f for f in candidate_files if str(f) not in known]

    imported = 0
    for path in new_files:
        try:
            if ingest_file(config["db_path"], path, config):
                imported += 1
        except Exception:
            logger.exception("Failed to import race file %s", path)

    return imported


def run_forever(config: dict) -> None:
    """Blocking loop: scan on startup, then poll at the configured interval."""
    db.init_db(config["db_path"])
    logger.info("Watching %s for new race files", config["watch_dir"])
    while True:
        imported = scan_once(config)
        if imported:
            logger.info("Imported %d new race(s)", imported)
        time.sleep(config["poll_interval_seconds"])
