"""Frozen structural fingerprint for the operational SQLite schema."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

EXPECTED_SCHEMA_FINGERPRINT = "bce3a094bcb0118f3fa0b550b7b2993c2eb862cc7ab03dbaf6484f5695207ce2"


class SchemaFingerprintError(RuntimeError):
    """The live database is not the exact frozen schema-v1 shape."""


def _pragma(connection: sqlite3.Connection, pragma: str, name: str) -> list[list[Any]]:
    quoted = name.replace('"', '""')
    return [list(row) for row in connection.execute(f'PRAGMA {pragma}("{quoted}")').fetchall()]


def _normalized_sql(value: str | None) -> str | None:
    return None if value is None else " ".join(value.split())


def schema_descriptor(connection: sqlite3.Connection) -> dict[str, Any]:
    objects = connection.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' "
        "ORDER BY type,name"
    ).fetchall()
    object_rows = [
        {"type": row[0], "name": row[1], "table": row[2], "sql": _normalized_sql(row[3])} for row in objects
    ]
    table_names = sorted(row[1] for row in objects if row[0] == "table")
    tables: dict[str, Any] = {}
    for table_name in table_names:
        indexes = _pragma(connection, "index_list", table_name)
        tables[table_name] = {
            "columns": _pragma(connection, "table_info", table_name),
            "foreign_keys": _pragma(connection, "foreign_key_list", table_name),
            "indexes": [
                {
                    "identity": {
                        "name": row[1],
                        "unique": row[2],
                        "origin": row[3],
                        "partial": row[4],
                    },
                    "columns": _pragma(connection, "index_xinfo", str(row[1])),
                    "sql": _normalized_sql(
                        (
                            connection.execute(
                                "SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (row[1],)
                            ).fetchone()
                            or [None]
                        )[0]
                    ),
                }
                for row in indexes
            ],
        }
    return {
        "user_version": int(connection.execute("PRAGMA user_version").fetchone()[0]),
        "objects": object_rows,
        "tables": tables,
    }


def schema_fingerprint(connection: sqlite3.Connection) -> str:
    encoded = json.dumps(
        schema_descriptor(connection), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_schema_fingerprint(connection: sqlite3.Connection) -> None:
    if schema_fingerprint(connection) != EXPECTED_SCHEMA_FINGERPRINT:
        raise SchemaFingerprintError("SQLite schema fingerprint differs from frozen schema v1")
