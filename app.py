import hmac
import os
import sqlite3

from flask import Flask, Response, redirect, render_template, request, url_for


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
                    "email TEXT NOT NULL, major TEXT NOT NULL)"
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
        if not all(fields.values()) or "@" not in fields["email"]:
            return render_template(
                "signup.html", error="Please fill in every field with a valid email.", **fields
            ), 400

        run(
            "INSERT INTO signups (name, email, major) VALUES (?, ?, ?)",
            (fields["name"], fields["email"], fields["major"]),
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
        signups = run("SELECT name, email, major FROM signups ORDER BY id")
        return render_template("admin.html", signups=signups)

    return app


app = create_app()
