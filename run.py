"""Entry point: runs the folder watcher in the background and serves the dashboard.

Usage:
    python run.py

Configure the watch directory, database path, and points rules in config.json
(see championship_tracker/config.py for defaults and available keys).
"""

import logging
import threading

from championship_tracker.app import create_app
from championship_tracker.config import load_config
from championship_tracker.watcher import run_forever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main():
    config = load_config()

    if config.get("run_watcher", True):
        watcher_thread = threading.Thread(target=run_forever, args=(config,), daemon=True)
        watcher_thread.start()

    app = create_app(config)
    app.run(host=config["web_host"], port=config["web_port"])


if __name__ == "__main__":
    main()
