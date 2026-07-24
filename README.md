# Pits-n-Giggles Championship Tracker

A companion app for [Pits n' Giggles](https://github.com/ashwin-nat/pits-n-giggles) that turns
open-lobby race results into an ongoing viewer championship.

Every race you host in Pits n' Giggles gets auto-saved as a JSON file. This app watches for
those files, pulls the final classification (position, points, status) out of them, and keeps
a running points table across all your races — with a small web dashboard for standings and
race history.

## How it works

- **Watcher** (`championship_tracker/watcher.py`) polls Pits n' Giggles' `data/<date>/race-info/`
  folder for new saved race JSON files and imports any it hasn't seen yet.
- **Points**: uses the race's own `points` field if the lobby had the in-game points setting on
  (it already matches the standard F1 scale). If a lobby has points turned off, it falls back to
  computing them from finishing position using the scale in `config.json`. A fastest-lap bonus
  point (top 10 finishers only, matching real F1 rules) is added on top and can be disabled.
- **Driver identity**: since these are open lobbies with no fixed roster, drivers are matched by
  their in-game name across races. Viewers with restricted broadcast/privacy settings show up as
  an anonymized placeholder (e.g. `221 #45`) — those are never auto-merged across races (the same
  placeholder can be a different person next time), and instead land on the **Admin** page for you
  to merge into the right driver, or rename, once you recognize who it was.
- **Dashboard** (Flask app in `championship_tracker/app.py`): standings, race-by-race results, and
  the admin screen above.

## Setup

```bash
pip install -r requirements.txt
cp config.json.example config.json
# edit config.json: set watch_dir to your Pits n' Giggles "data" folder
python run.py
```

The dashboard runs at `http://localhost:5000` by default (see `web_host`/`web_port` in
`config.json`). The watcher runs in the background in the same process and re-scans the data
folder every `poll_interval_seconds`.

## Configuration

All settings live in `config.json` (see `config.json.example`); anything not overridden falls
back to the defaults in `championship_tracker/config.py`.

## Making it public to viewers

Before exposing this anywhere: set `admin_password` in `config.json` to something real. The
`/admin` page (driver merge/rename) is HTTP Basic Auth-protected using
`admin_username`/`admin_password`, and is **disabled entirely** (404) if `admin_password` is left
blank — it's meant to only ever be used by you, never by viewers. The standings, race history, and
race detail pages have no auth and are meant to be public.

There are two ways to host this publicly, depending on whether the dashboard runs on the same
machine as Pits n' Giggles or on a separate always-on server:

### Option A: same machine, tunneled out

Run `python run.py` as usual (it watches the local data folder and serves the dashboard together),
then put a [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
in front of `http://localhost:5000` if your domain's DNS is on Cloudflare. Only reachable while
that machine and both processes are running.

### Option B: dashboard on a separate always-on server (e.g. a VPS)

Since the server hosting the dashboard doesn't have the Pits n' Giggles data folder, race results
have to be pushed to it instead of read off disk:

- **On the server**: set `run_watcher: false` and `upload_token` (a shared secret) in `config.json`,
  and serve `wsgi:app` with a production WSGI server (see `deploy/championship-tracker.service` for
  a systemd unit running gunicorn, and `deploy/Caddyfile` for a reverse proxy + automatic HTTPS in
  front of it).
- **On the machine that actually runs Pits n' Giggles**: run `python run_uploader.py` instead of
  `run.py`. Configure it via `uploader_config.json` (see `uploader_config.json.example`) with the
  local `watch_dir`, the server's public `remote_url` (e.g.
  `https://standings.gremigaming.com/api/ingest`), and the same `upload_token` as the server. It
  watches the data folder and POSTs new race files to the server; already-uploaded files are
  tracked locally so nothing gets re-sent.
- `POST /api/ingest` requires an `X-Upload-Token` header matching the server's `upload_token`, and
  is disabled (404) if `upload_token` is left blank on the server.

## Tests

```bash
pip install -r requirements.txt pytest
pytest tests/
```

`tests/fixtures/sample_race.json` is a trimmed real race export used to test parsing, points
computation, and driver-identity resolution without needing a live Pits n' Giggles instance.
