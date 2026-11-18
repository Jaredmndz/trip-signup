# trip-signup

A small Flask app where students register interest in a study abroad trip.
Students fill in their name, email and major. Organizers view every signup on a
password-protected admin page.

## Pages

| Path      | What it does |
|-----------|--------------|
| `/`       | Sign-up form (name, email, major, number of guests). Name, email and major are required and the email must contain `@`. Guests is optional (default 0) and must be a whole number from 0 to 10. A bad submission shows the form again with an error. |
| `/count`  | Public JSON summary: `{"rsvps": <signups>, "headcount": <signups + guests>}`. Never includes names or emails. |
| `/thanks` | Confirmation page shown after a successful sign-up. |
| `/admin`  | Table of all signups and a count. Protected by HTTP Basic Auth. Any username works; the password must match `ADMIN_PASSWORD`. |

If `ADMIN_PASSWORD` is unset or empty, `/admin` stays locked for everyone.

## Setup

You need Python 3.14 and [Pipenv](https://pipenv.pypa.io/).

```sh
pipenv install --dev
```

Create a `.env` file in the project root. `pipenv run` loads it automatically:

```sh
ADMIN_PASSWORD=choose-a-strong-password
```

`.env` is git-ignored. Don't commit it.

## Run

```sh
pipenv run flask run --debug --port 5001
```

Then open http://127.0.0.1:5001.

For a production-style server, gunicorn is included:

```sh
pipenv run gunicorn app:app
```

## Test

```sh
pipenv run pytest -q
```

Tests use a temporary database, so they never touch `rsvp.db`.

## How it works

- **Storage:** SQLite in `rsvp.db`, accessed through Python's built-in
  `sqlite3` module (no ORM). The `signups` table is created automatically on
  first use. `rsvp.db` is git-ignored.
- **Templates:** Plain Jinja templates in `templates/`, styled with Bootstrap 5
  CSS from a CDN (with an integrity hash). The pages use no JavaScript.
- **Code:** Everything is in `app.py`. `create_app(database)` builds the app,
  which lets the tests point it at a temporary database file.

## Project layout

```
app.py            Flask app: routes, validation, database access
templates/        base, signup, thanks and admin pages
test_app.py       pytest suite
Pipfile(.lock)    dependencies (flask, gunicorn; pytest for dev)
```
