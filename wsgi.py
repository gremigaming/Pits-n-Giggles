"""WSGI entry point for production deployment, e.g. `gunicorn wsgi:app`.

Only serves the dashboard - does not start the local folder watcher, since a
server deployment typically has no Pits-n-Giggles data folder to watch (set
run_watcher: false in config.json; races arrive via POST /api/ingest from
uploader.py running on the machine that does have that folder).
"""

from championship_tracker.app import create_app

app = create_app()
