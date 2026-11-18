import sqlite3

import pytest

from app import create_app


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


ADMIN_PASSWORD = "test-secret"


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN_PASSWORD)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def rows(db_path):
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT name, email, major FROM signups").fetchall()
    finally:
        conn.close()


def test_form_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b'name="email"' in resp.data


def test_signup_saves_and_redirects(client, db_path):
    resp = client.post(
        "/", data={"name": "Ada", "email": "ada@example.edu", "major": "Math"}
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/thanks")
    assert rows(db_path) == [("Ada", "ada@example.edu", "Math")]


def test_thanks_page(client):
    resp = client.get("/thanks")
    assert resp.status_code == 200
    assert b"Thanks" in resp.data


@pytest.mark.parametrize(
    "data",
    [
        {"name": "", "email": "ada@example.edu", "major": "Math"},
        {"name": "Ada", "email": "not-an-email", "major": "Math"},
        {"name": "Ada", "email": "ada@example.edu"},
    ],
)
def test_invalid_signup_rejected(client, db_path, data):
    resp = client.post("/", data=data)
    assert resp.status_code == 400
    assert rows(db_path) == []


def sign_up(client, name, email, major):
    client.post("/", data={"name": name, "email": email, "major": major})


def test_admin_requires_password(client):
    resp = client.get("/admin")
    assert resp.status_code == 401
    assert "Basic" in resp.headers["WWW-Authenticate"]


def test_admin_rejects_wrong_password(client):
    resp = client.get("/admin", auth=("admin", "wrong"))
    assert resp.status_code == 401


def test_admin_lists_every_signup(client):
    sign_up(client, "Ada", "ada@example.edu", "Math")
    sign_up(client, "Grace", "grace@example.edu", "Computer Science")
    resp = client.get("/admin", auth=("admin", ADMIN_PASSWORD))
    assert resp.status_code == 200
    for text in ["Ada", "ada@example.edu", "Math",
                 "Grace", "grace@example.edu", "Computer Science"]:
        assert text.encode() in resp.data


def test_admin_with_no_signups(client):
    resp = client.get("/admin", auth=("admin", ADMIN_PASSWORD))
    assert resp.status_code == 200
    assert b"No signups yet" in resp.data


def test_admin_escapes_html(client):
    sign_up(client, "<script>x</script>", "evil@example.edu", "Math")
    resp = client.get("/admin", auth=("admin", ADMIN_PASSWORD))
    assert b"<script>x</script>" not in resp.data
    assert b"&lt;script&gt;" in resp.data


def test_admin_locked_when_password_unset(db_path, monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    client = create_app(str(db_path)).test_client()
    assert client.get("/admin", auth=("admin", "")).status_code == 401


@pytest.mark.parametrize("path", ["/", "/thanks", "/admin"])
def test_pages_use_bootstrap_css_only(client, path):
    resp = client.get(path, auth=("admin", ADMIN_PASSWORD))
    assert b"bootstrap@5.3.3/dist/css/bootstrap.min.css" in resp.data
    assert b'integrity="sha384-' in resp.data
    assert b"<script" not in resp.data


def test_railway_start_command_points_at_real_app():
    import importlib
    import json
    from pathlib import Path

    from flask import Flask

    config = json.loads((Path(__file__).parent / "railway.json").read_text())
    command = config["deploy"]["startCommand"].split()
    assert command[0] == "gunicorn"
    module_name, attr = command[1].split(":")
    module = importlib.import_module(module_name)
    assert isinstance(getattr(module, attr), Flask)


def guest_counts(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return [r[0] for r in conn.execute("SELECT guests FROM signups ORDER BY id")]
    finally:
        conn.close()


def test_signup_saves_guests(client, db_path):
    client.post("/", data={"name": "Ada", "email": "ada@example.edu",
                           "major": "Math", "guests": "2"})
    client.post("/", data={"name": "Grace", "email": "grace@example.edu",
                           "major": "CS"})
    assert guest_counts(db_path) == [2, 0]


@pytest.mark.parametrize("guests", ["-1", "abc", "1.5", "11"])
def test_invalid_guests_rejected(client, db_path, guests):
    resp = client.post("/", data={"name": "Ada", "email": "ada@example.edu",
                                  "major": "Math", "guests": guests})
    assert resp.status_code == 400
    assert b"Guests must be" in resp.data
    assert rows(db_path) == []


def test_count_with_no_signups(client):
    resp = client.get("/count")
    assert resp.status_code == 200
    assert resp.get_json() == {"rsvps": 0, "headcount": 0}


def test_count_adds_guests_to_headcount(client):
    for name, guests in [("Ada", "2"), ("Grace", "0"), ("Alan", "3")]:
        client.post("/", data={"name": name, "email": f"{name}@example.edu",
                               "major": "Math", "guests": guests})
    resp = client.get("/count")
    assert resp.status_code == 200
    assert resp.get_json() == {"rsvps": 3, "headcount": 8}
    assert b"@" not in resp.data


def test_admin_shows_guests(client):
    client.post("/", data={"name": "Ada", "email": "ada@example.edu",
                           "major": "Math", "guests": "4"})
    resp = client.get("/admin", auth=("admin", ADMIN_PASSWORD))
    assert b"<th>Guests</th>" in resp.data
    assert b"<td>4</td>" in resp.data


def test_existing_database_without_guests_column_is_upgraded(db_path, client):
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute("CREATE TABLE signups (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                     "email TEXT NOT NULL, major TEXT NOT NULL)")
        conn.execute("INSERT INTO signups (name, email, major) VALUES (?, ?, ?)",
                     ("Old", "old@example.edu", "History"))
    conn.close()
    assert client.get("/count").get_json() == {"rsvps": 1, "headcount": 1}
    client.post("/", data={"name": "New", "email": "new@example.edu",
                           "major": "Art", "guests": "1"})
    assert client.get("/count").get_json() == {"rsvps": 2, "headcount": 3}


def test_default_database_is_rsvp_db(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN_PASSWORD)
    assert create_app().config["DATABASE"] == "rsvp.db"
