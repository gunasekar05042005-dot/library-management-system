import sqlite3

import click
from flask import current_app, g


def connect(path):
    # isolation_level=None -> autocommit; the borrowing service opens its own
    # transactions explicitly with BEGIN IMMEDIATE (see services/borrowing.py).
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row           # access columns by name
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite needs this per connection
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with current_app.open_resource("schema.sql") as f:
        get_db().executescript(f.read().decode("utf-8"))


@click.command("init-db")
def init_db_command():
    """Create the tables (safe to run more than once)."""
    init_db()
    click.echo("Database ready.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
