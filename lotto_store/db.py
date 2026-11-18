"""SQLite connection management for the XSMN latest-state database."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH: Path = _PROJECT_ROOT / "lottery_latest.db"
DEFAULT_SCHEMA_PATH: Path = _PROJECT_ROOT / "schema.sql"


def open_lottery_db(
    db_path: str | Path | None = None,
    *,
    schema_path: str | Path | None = None,
) -> sqlite3.Connection:
    """Open the SQLite database and ensure the latest-state schema exists.

    Args:
        db_path: Path to the SQLite database file (defaults to `<root>/lottery_latest.db`).
                 Use `":memory:"` for an in-memory database during tests.
        schema_path: Path to `schema.sql` (defaults to `<root>/schema.sql`).
    """
    resolved_db = DEFAULT_DB_PATH if db_path is None else db_path
    resolved_schema = DEFAULT_SCHEMA_PATH if schema_path is None else Path(schema_path)

    if str(resolved_db) != ":memory:":
        Path(resolved_db).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(resolved_db))
    conn.row_factory = sqlite3.Row
    conn.executescript(resolved_schema.read_text(encoding="utf-8"))
    return conn


@contextmanager
def lottery_db_session(
    db_path: str | Path | None = None,
    *,
    schema_path: str | Path | None = None,
) -> Iterator[sqlite3.Connection]:
    """Context manager that opens the database and guarantees closing it on exit."""
    conn = open_lottery_db(db_path, schema_path=schema_path)
    try:
        yield conn
    finally:
        conn.close()
