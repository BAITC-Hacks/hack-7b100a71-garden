"""PostgreSQL connections and checked-in migrations for Supabase."""
import hashlib
from pathlib import Path
import re

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"


def validate_schema(schema):
    if not isinstance(schema, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
        raise ValueError("Database schema must be a lowercase SQL identifier")
    return schema


def connect(database_url):
    # Supabase's transaction pooler cannot use server-side prepared statements.
    # Keep an explicit sslmode (e.g. verify-full or local disable); require TLS otherwise.
    options = conninfo_to_dict(database_url)
    return psycopg.connect(
        database_url, row_factory=dict_row, prepare_threshold=None,
        connect_timeout=10, sslmode=options.get("sslmode", "require"),
    )


def migrate(database_url, *, schema="career_quest"):
    """Apply new migrations atomically; never silently edit an applied migration."""
    validate_schema(schema)
    applied = []
    with connect(database_url) as connection:
        connection.execute("SET LOCAL lock_timeout = '10s'")
        connection.execute("SET LOCAL statement_timeout = '60s'")
        connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
                           (schema, "career_quest_migrations"))
        connection.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        connection.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC").format(sql.Identifier(schema)))
        table = sql.Identifier(schema, "schema_migrations")
        connection.execute(sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
                name text PRIMARY KEY, checksum text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
        """).format(table))
        connection.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(table))
        known = {row["name"]: row["checksum"] for row in
                 connection.execute(sql.SQL("SELECT name, checksum FROM {}").format(table))}
        paths = sorted(MIGRATIONS.glob("*.sql"))
        if set(known) - {path.name for path in paths}:
            raise ValueError("Database has migrations newer than this backend")
        for path in paths:
            source = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(source.encode()).hexdigest()
            if path.name in known:
                if known[path.name] != checksum:
                    raise ValueError("An applied database migration has changed: " + path.name)
                continue
            # Schema names are validated identifiers; custom schemas isolate integration tests.
            connection.execute(source.replace("career_quest", schema), prepare=False)
            connection.execute(sql.SQL("INSERT INTO {} (name, checksum) VALUES (%s, %s)").format(table),
                               (path.name, checksum))
            applied.append(path.name)
    return applied
