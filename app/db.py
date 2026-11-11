import sqlite3

import click
from flask import current_app, g


def connect(path, timeout=10):
    # isolation_level=None -> autocommit; services open their own transactions explicitly
    # with BEGIN IMMEDIATE. WAL lets readers continue while a writer is working.
    conn = sqlite3.connect(path, timeout=timeout, isolation_level=None)
    conn.row_factory = sqlite3.Row            # access columns by name
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite needs this per connection
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"], current_app.config["DB_TIMEOUT"])
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def migrate(db):
    """Upgrade a database made by an older version (schema.sql only creates missing tables)."""
    columns = {row["name"] for row in db.execute("PRAGMA table_info(books)")}
    for name in ("cover_url", "description"):
        if name not in columns:
            db.execute(f"ALTER TABLE books ADD COLUMN {name} TEXT")


def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))
    migrate(db)


@click.command("init-db")
def init_db_command():
    """Create or upgrade the tables (safe to run more than once)."""
    init_db()
    click.echo("Database ready.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
