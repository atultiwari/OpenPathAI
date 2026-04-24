"""Audit DB schema bootstrap + idempotency."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from openpathai.safety.audit import AuditDB
from openpathai.safety.audit.schema import SCHEMA_VERSION, TABLE_NAMES


def _existing_tables(path: Path) -> set[str]:
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def test_schema_version_is_one() -> None:
    assert SCHEMA_VERSION == 1


def test_bootstrap_creates_every_table(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    AuditDB.open_path(db_path)
    tables = _existing_tables(db_path)
    for name in TABLE_NAMES:
        assert name in tables, f"expected table {name!r} in {tables}"


def test_schema_info_row_present(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    AuditDB.open_path(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT version FROM schema_info ORDER BY version DESC LIMIT 1"
        ).fetchone()
    assert row is not None
    assert row[0] == SCHEMA_VERSION


def test_re_open_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    AuditDB.open_path(db_path)
    AuditDB.open_path(db_path)  # second open must not raise
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM schema_info").fetchone()
    # Still exactly one schema_info row.
    assert rows[0] == 1


def test_wal_journal_mode(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    AuditDB.open_path(db_path)
    with sqlite3.connect(db_path) as conn:
        (mode,) = conn.execute("PRAGMA journal_mode").fetchone()
    assert mode.lower() == "wal"
