"""Relational persistence with coherent reads and serialized PostgreSQL writes."""
import hashlib
import json
from pathlib import Path
from typing import Optional

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from backend.data.postgres import connect, validate_schema
from backend.data.postgres_codec import TABLE_KEYS, decode_dataset, encode_dataset
from backend.data.repository import DatasetRepository, MutableState, validate_runtime_state
from backend.data.validation import validate_dataset
from backend.errors import AppError
from backend.models.domain import DatasetMeta


class PostgresRepository(DatasetRepository):
    """Use the existing service/view contract without keeping a stale process cache."""

    def __init__(self, database_url: str, *, schema="career_quest"):
        self._database_url = database_url
        self._schema = validate_schema(schema)

    def _table(self, name):
        return sql.Identifier(self._schema, name)

    @staticmethod
    def _timeouts(connection):
        connection.execute("SET LOCAL lock_timeout = '10s'")
        connection.execute("SET LOCAL statement_timeout = '30s'")

    def initialize(self, directory: Path, legacy_state_path: Optional[Path] = None):
        """Seed an empty database once, importing a legacy snapshot when present.

        Existing databases are authoritative: no source files are needed on restart.
        Schema changes are explicit through `python -m backend.db init`.
        """
        try:
            with connect(self._database_url) as connection:
                self._timeouts(connection)
                connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
                                   (self._schema, "career_quest_seed"))
                existing = connection.execute(sql.SQL("SELECT * FROM {} WHERE id = 1").format(
                    self._table("dataset_state"))).fetchone()
                if existing is not None:
                    self._check_metadata(existing)
                    return False
                from backend.data.loader import load_dataset
                original = load_dataset(directory)
                legacy = DatasetRepository(original, state_path=legacy_state_path)
                state = legacy._state.clone()
                canonical = json.dumps(original.model_dump(mode="json"), sort_keys=True,
                                       separators=(",", ":"), ensure_ascii=False)
                fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
                meta = state.dataset.meta
                connection.execute(sql.SQL("""
                    INSERT INTO {} (id, schema_version, source_fingerprint, version,
                                    dataset_name, dataset_version, as_of_date)
                    VALUES (1, 1, %s, %s, %s, %s, %s)
                """).format(self._table("dataset_state")),
                    (fingerprint, state.version, meta.dataset, meta.version, meta.as_of_date))
                self._write_state(connection, None, state)
                return True
        except psycopg.errors.UndefinedTable:
            raise AppError("database_not_initialized",
                           "Run python -m backend.db init to initialize the database", 503) from None
        except psycopg.Error:
            raise AppError("database_unavailable", "Could not initialize database storage", 503) from None

    @staticmethod
    def _check_metadata(metadata):
        if metadata is None or metadata["schema_version"] != 1:
            raise AppError("database_not_initialized",
                           "Run python -m backend.db init with a compatible backend", 503)

    def _metadata(self, connection, *, lock=False):
        query = sql.SQL("SELECT * FROM {} WHERE id = 1{}").format(
            self._table("dataset_state"), sql.SQL(" FOR UPDATE" if lock else ""))
        metadata = connection.execute(query).fetchone()
        self._check_metadata(metadata)
        return metadata

    @property
    def version(self):
        try:
            with connect(self._database_url) as connection:
                self._timeouts(connection)
                return self._metadata(connection)["version"]
        except psycopg.Error:
            raise AppError("database_unavailable", "Could not read database storage", 503) from None

    def _load_state(self, connection, metadata, *, receipts=True):
        tables = list(TABLE_KEYS) + ["runtime_completions"]
        if receipts:
            tables.append("idempotency_receipts")
        # Pipeline avoids a network round trip for every relation in a snapshot.
        cursors = {}
        with connection.pipeline():
            for table in tables:
                cursors[table] = connection.execute(sql.SQL("SELECT * FROM {}").format(self._table(table)))
        rows = {table: cursor.fetchall() for table, cursor in cursors.items()}
        try:
            dataset = decode_dataset(rows, DatasetMeta(
                dataset=metadata["dataset_name"], version=metadata["dataset_version"],
                as_of_date=metadata["as_of_date"],
            ))
            completed = [row["record_id"] for row in sorted(rows["runtime_completions"],
                                                           key=lambda row: row["position"])]
            saved = {row["receipt_key"]: {"fingerprint": row["fingerprint"], "result": row["result"]}
                     for row in rows.get("idempotency_receipts", [])}
            return validate_runtime_state(MutableState(dataset, metadata["version"], saved, completed))
        except ValueError:
            raise AppError("database_state_invalid",
                           "Stored database state is invalid; restore a verified backup", 503) from None

    def view(self):
        try:
            with connect(self._database_url) as connection:
                connection.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
                connection.read_only = True
                self._timeouts(connection)
                state = self._load_state(connection, self._metadata(connection), receipts=False)
                return state.view()
        except psycopg.Error:
            raise AppError("database_unavailable", "Could not read database storage", 503) from None

    def mutate(self, operation):
        try:
            with connect(self._database_url) as connection:
                # READ COMMITTED after this row lock sees the previous writer's commit.
                connection.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
                self._timeouts(connection)
                before = self._load_state(connection, self._metadata(connection, lock=True))
                candidate = before.clone()
                candidate.version += 1
                result = operation(candidate)
                if candidate.dirty:
                    candidate.dataset = validate_dataset(candidate.dataset)
                    self._write_state(connection, before, candidate)
            return result
        except psycopg.Error:
            # An interrupted COMMIT can have an unknown outcome. Retrying the same
            # idempotency key resolves that case without awarding progress twice.
            raise AppError("database_write_failed",
                           "Database write could not be confirmed; retry with the same Idempotency-Key",
                           503) from None

    @staticmethod
    def _state_rows(state):
        if state is None:
            return {}
        rows = encode_dataset(state.dataset)
        rows["runtime_completions"] = [
            {"record_id": record_id, "position": position}
            for position, record_id in enumerate(state.completed_record_ids)
        ]
        rows["idempotency_receipts"] = [
            {"receipt_key": key, "fingerprint": value["fingerprint"], "result": value["result"]}
            for key, value in state.receipts.items()
        ]
        return rows

    def _write_state(self, connection, before, after):
        old_rows, new_rows = self._state_rows(before), self._state_rows(after)
        keys = {**TABLE_KEYS, "runtime_completions": ("record_id",),
                "idempotency_receipts": ("receipt_key",)}
        with connection.pipeline():
            for table, primary_key in keys.items():
                key = lambda row: tuple(row[column] for column in primary_key)
                old = {key(row): row for row in old_rows.get(table, [])}
                new = {key(row): row for row in new_rows.get(table, [])}
                removed = list(old.keys() - new.keys())
                if removed:
                    where = sql.SQL(" AND ").join(sql.SQL("{} = %s").format(sql.Identifier(column))
                                                   for column in primary_key)
                    with connection.cursor() as cursor:
                        cursor.executemany(sql.SQL("DELETE FROM {} WHERE {}").format(
                            self._table(table), where), removed)
                changed = [row for identity, row in new.items() if old.get(identity) != row]
                if not changed:
                    continue
                columns = tuple(changed[0])
                updates = sql.SQL(", ").join(sql.SQL("{} = EXCLUDED.{}").format(
                    sql.Identifier(column), sql.Identifier(column))
                    for column in columns if column not in primary_key)
                query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {}").format(
                    self._table(table), sql.SQL(", ").join(map(sql.Identifier, columns)),
                    sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                    sql.SQL(", ").join(map(sql.Identifier, primary_key)), updates)
                values = [tuple(Jsonb(row[column]) if column == "result" else row[column]
                                for column in columns) for row in changed]
                with connection.cursor() as cursor:
                    cursor.executemany(query, values)
            meta = after.dataset.meta
            connection.execute(sql.SQL("""
                UPDATE {} SET version = %s, dataset_name = %s, dataset_version = %s,
                              as_of_date = %s WHERE id = 1
            """).format(self._table("dataset_state")),
                (after.version, meta.dataset, meta.version, meta.as_of_date))
