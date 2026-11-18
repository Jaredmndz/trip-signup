import hmac
import os
import sqlite3

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

MAX_GUESTS = 10


def create_app(database="signups.db"):
    app = Flask(__name__)
    app.config["DATABASE"] = database

    app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "")

    def run(sql, params=()):
        conn = sqlite3.connect(app.config["DATABASE"])
        try:
            with conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS signups ("
                    "id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                    "email TEXT NOT NULL, major TEXT NOT NULL, "
                    "guests INTEGER NOT NULL DEFAULT 0)"
                )
                columns = [row[1] for row in conn.execute("PRAGMA table_info(signups)")]
                if "guests" not in columns:
                    conn.execute(
                        "ALTER TABLE signups ADD COLUMN guests INTEGER NOT NULL DEFAULT 0"
                    )
                return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def is_admin():
        expected = app.config["ADMIN_PASSWORD"]
        auth = request.authorization
        return bool(expected) and auth is not None and hmac.compare_digest(
            (auth.password or "").encode(), expected.encode()
        )

    @app.route("/", methods=["GET", "POST"])
    def signup():
        if request.method == "GET":
            return render_template("signup.html")

        fields = {k: request.form.get(k, "").strip() for k in ("name", "email", "major")}
        guests = request.form.get("guests", "").strip() or "0"
        if not all(fields.values()) or "@" not in fields["email"]:
            return render_template(
                "signup.html", error="Please fill in every field with a valid email.",
                guests=guests, **fields
            ), 400
        if not guests.isdigit() or int(guests) > MAX_GUESTS:
            return render_template(
                "signup.html", error=f"Guests must be a whole number from 0 to {MAX_GUESTS}.",
                guests=guests, **fields
            ), 400

        run(
            "INSERT INTO signups (name, email, major, guests) VALUES (?, ?, ?, ?)",
            (fields["name"], fields["email"], fields["major"], int(guests)),
        )
        return redirect(url_for("thanks"))

    @app.route("/thanks")
    def thanks():
        return render_template("thanks.html")

    @app.route("/admin")
    def admin():
        if not is_admin():
            return Response(
                "Password required.", 401,
                {"WWW-Authenticate": 'Basic realm="Trip signups admin"'},
            )
        signups = run("SELECT name, email, major, guests FROM signups ORDER BY id")
        return render_template("admin.html", signups=signups)

    @app.route("/count")
    def count():
        rsvps, guests = run("SELECT COUNT(*), COALESCE(SUM(guests), 0) FROM signups")[0]
        return jsonify(rsvps=rsvps, headcount=rsvps + guests)

    return app


app = create_app()
