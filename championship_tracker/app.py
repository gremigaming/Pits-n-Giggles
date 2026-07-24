"""Flask web app: standings, race history, and driver-identity admin."""

import logging

from flask import Flask, abort, redirect, render_template, request, url_for

from . import db
from .config import load_config

logger = logging.getLogger(__name__)


def create_app(config: dict | None = None) -> Flask:
    config = config or load_config()
    db.init_db(config["db_path"])

    app = Flask(__name__)
    app.config["TRACKER_CONFIG"] = config

    @app.template_filter("lap_time")
    def format_lap_time(ms):
        if ms is None:
            return "-"
        minutes, rest = divmod(ms, 60000)
        seconds, millis = divmod(rest, 1000)
        return f"{minutes}:{seconds:02d}.{millis:03d}"

    @app.template_filter("race_time")
    def format_race_time(seconds):
        if seconds is None:
            return "-"
        total_ms = round(seconds * 1000)
        return format_lap_time(total_ms)

    @app.route("/")
    def standings():
        with db.connect(config["db_path"]) as conn:
            rows = conn.execute(
                """
                SELECT
                    d.id AS driver_id,
                    d.display_name,
                    d.needs_review,
                    COUNT(*) AS races_entered,
                    SUM(r.points + r.bonus_points) AS total_points,
                    SUM(CASE WHEN r.position = 1 THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN r.position <= 3 THEN 1 ELSE 0 END) AS podiums,
                    SUM(r.bonus_points) AS fastest_laps
                FROM results r
                JOIN drivers d ON d.id = r.driver_id
                WHERE d.needs_review = 0
                GROUP BY d.id
                ORDER BY total_points DESC, wins DESC
                """
            ).fetchall()
        return render_template("standings.html", standings=rows)

    @app.route("/races")
    def races():
        with db.connect(config["db_path"]) as conn:
            rows = conn.execute(
                "SELECT * FROM races ORDER BY race_timestamp DESC"
            ).fetchall()
        return render_template("races.html", races=rows)

    @app.route("/race/<session_uid>")
    def race_detail(session_uid):
        with db.connect(config["db_path"]) as conn:
            race = conn.execute(
                "SELECT * FROM races WHERE session_uid = ?", (session_uid,)
            ).fetchone()
            if race is None:
                abort(404)
            results = conn.execute(
                """
                SELECT r.*, d.display_name
                FROM results r
                JOIN drivers d ON d.id = r.driver_id
                WHERE r.session_uid = ?
                ORDER BY r.position ASC
                """,
                (session_uid,),
            ).fetchall()
        return render_template("race_detail.html", race=race, results=results)

    @app.route("/admin")
    def admin():
        with db.connect(config["db_path"]) as conn:
            pending = conn.execute(
                """
                SELECT d.id AS driver_id, d.display_name, r.session_uid, r.alias_used,
                       r.position, ra.track, ra.race_timestamp
                FROM drivers d
                JOIN results r ON r.driver_id = d.id
                JOIN races ra ON ra.session_uid = r.session_uid
                WHERE d.needs_review = 1
                ORDER BY ra.race_timestamp DESC
                """
            ).fetchall()
            known_drivers = conn.execute(
                "SELECT id, display_name FROM drivers WHERE needs_review = 0 ORDER BY display_name"
            ).fetchall()
        return render_template("admin.html", pending=pending, known_drivers=known_drivers)

    @app.route("/admin/merge", methods=["POST"])
    def admin_merge():
        from_driver_id = int(request.form["from_driver_id"])
        into_driver_id = int(request.form["into_driver_id"])
        with db.connect(config["db_path"]) as conn:
            db.merge_driver(conn, from_driver_id, into_driver_id)
        return redirect(url_for("admin"))

    @app.route("/admin/rename", methods=["POST"])
    def admin_rename():
        driver_id = int(request.form["driver_id"])
        new_name = request.form["new_name"].strip()
        if not new_name:
            abort(400)
        with db.connect(config["db_path"]) as conn:
            db.rename_driver(conn, driver_id, new_name)
        return redirect(url_for("admin"))

    return app
