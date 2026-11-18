"""Read, Write, Query, and Delete interfaces for `latest_lottery_results`."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Callable, Literal, Mapping, Sequence, TypeVar

from .db import lottery_db_session
from .models import LatestLotteryResult, LotterySyncInput, validate_draw_date
from .provinces import XSMN_PROVINCE_MAP, normalize_province_code

_T = TypeVar("_T")

_UPSERT_SQL = """
INSERT OR REPLACE INTO latest_lottery_results (
    province_code,
    draw_date,
    prizes,
    updated_at
) VALUES (?, ?, ?, ?)
"""

_SELECT_COLUMNS = "province_code, draw_date, prizes, updated_at"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _coerce_sync_input(item: LotterySyncInput | Mapping[str, Any]) -> LotterySyncInput:
    if isinstance(item, LotterySyncInput):
        return item
    if isinstance(item, Mapping):
        return LotterySyncInput.from_dict(item)
    raise TypeError(f"Expected LotterySyncInput or Mapping, got {type(item).__name__}.")


def _run_with_connection(
    conn: sqlite3.Connection | None,
    db_path: str | Path | None,
    fn: Callable[[sqlite3.Connection], _T],
) -> _T:
    if conn is not None:
        return fn(conn)
    with lottery_db_session(db_path) as managed_conn:
        return fn(managed_conn)


# ---------------------------------------------------------------------------
# Write (Latest-State Overwrite)
# ---------------------------------------------------------------------------


def sync_results(
    items: Sequence[LotterySyncInput | Mapping[str, Any]],
    *,
    db_path: str | Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Atomically overwrite the latest lottery state for one or more provinces.

    Uses `INSERT OR REPLACE` inside a single SQLite transaction so each
    `province_code` retains at most one latest row.
    """
    normalized_items = [_coerce_sync_input(item) for item in items]
    if not normalized_items:
        return 0

    now_iso = _utc_now_iso()
    rows = [
        (item.province_code, item.draw_date, item.prizes.to_json(), now_iso)
        for item in normalized_items
    ]

    def _op(c: sqlite3.Connection) -> int:
        with c:
            c.executemany(_UPSERT_SQL, rows)
        return len(rows)

    return _run_with_connection(conn, db_path, _op)


def upsert_result(
    item: LotterySyncInput | Mapping[str, Any],
    *,
    db_path: str | Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> LatestLotteryResult:
    """Write or overwrite a single province's latest result and return the stored record."""
    normalized = _coerce_sync_input(item)
    now_iso = _utc_now_iso()

    def _op(c: sqlite3.Connection) -> LatestLotteryResult:
        with c:
            c.execute(
                _UPSERT_SQL,
                (
                    normalized.province_code,
                    normalized.draw_date,
                    normalized.prizes.to_json(),
                    now_iso,
                ),
            )
        return LatestLotteryResult(
            province_code=normalized.province_code,
            draw_date=normalized.draw_date,
            prizes=normalized.prizes,
            updated_at=now_iso,
        )

    return _run_with_connection(conn, db_path, _op)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def get_all_results(
    *,
    db_path: str | Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[LatestLotteryResult]:
    """Fetch the latest state for all stored provinces (newest draw_date first)."""

    def _op(c: sqlite3.Connection) -> list[LatestLotteryResult]:
        cursor = c.execute(
            f"""
            SELECT {_SELECT_COLUMNS}
            FROM latest_lottery_results
            ORDER BY draw_date DESC, province_code ASC
            """
        )
        return [LatestLotteryResult.from_row(row) for row in cursor.fetchall()]

    return _run_with_connection(conn, db_path, _op)


def get_result_by_province(
    province_code: str,
    *,
    validate_code: bool = True,
    db_path: str | Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> LatestLotteryResult | None:
    """Fetch the latest state for a single province by primary key."""
    code = normalize_province_code(province_code, validate=validate_code)

    def _op(c: sqlite3.Connection) -> LatestLotteryResult | None:
        cursor = c.execute(
            f"""
            SELECT {_SELECT_COLUMNS}
            FROM latest_lottery_results
            WHERE province_code = ?
            """,
            (code,),
        )
        row = cursor.fetchone()
        return LatestLotteryResult.from_row(row) if row is not None else None

    return _run_with_connection(conn, db_path, _op)


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def count_results(
    *,
    db_path: str | Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Return the number of province rows currently stored."""

    def _op(c: sqlite3.Connection) -> int:
        row = c.execute("SELECT COUNT(*) FROM latest_lottery_results").fetchone()
        return int(row[0]) if row is not None else 0

    return _run_with_connection(conn, db_path, _op)


def query_results(
    *,
    draw_date: str | None = None,
    draw_day: int | None = None,
    province_codes: Sequence[str] | None = None,
    search_number: str | None = None,
    match_mode: Literal["exact", "suffix"] = "exact",
    db_path: str | Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[LatestLotteryResult]:
    """Query latest lottery results with optional filters.

    Args:
        draw_date: Filter by exact draw date (`YYYY-MM-DD`).
        draw_day: Filter by weekly draw day (`0` = Sunday .. `6` = Saturday).
        province_codes: Filter by one or more province codes.
        search_number: Filter provinces whose prizes contain this number.
        match_mode: `"exact"` for full prize match or `"suffix"` for ending-digits match
                    (e.g. last 2 digits / lô).
    """
    clauses: list[str] = []
    params: list[Any] = []

    if draw_date is not None:
        clauses.append("draw_date = ?")
        params.append(validate_draw_date(draw_date))

    if province_codes is not None:
        codes = [normalize_province_code(code) for code in province_codes]
        if not codes:
            return []
        placeholders = ", ".join("?" for _ in codes)
        clauses.append(f"province_code IN ({placeholders})")
        params.extend(codes)

    if draw_day is not None:
        if not isinstance(draw_day, int) or isinstance(draw_day, bool) or not (0 <= draw_day <= 6):
            raise ValueError(f"draw_day must be an integer between 0 and 6, got {draw_day!r}")

    if search_number is not None:
        if not isinstance(search_number, str) or not search_number.isdigit():
            raise ValueError(f"search_number must be a digit string, got {search_number!r}")
        if match_mode not in ("exact", "suffix"):
            raise ValueError(f"match_mode must be 'exact' or 'suffix', got {match_mode!r}")

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    def _op(c: sqlite3.Connection) -> list[LatestLotteryResult]:
        cursor = c.execute(
            f"""
            SELECT {_SELECT_COLUMNS}
            FROM latest_lottery_results
            {where_sql}
            ORDER BY draw_date DESC, province_code ASC
            """,
            params,
        )
        results = [LatestLotteryResult.from_row(row) for row in cursor.fetchall()]

        if draw_day is not None:
            results = [
                r
                for r in results
                if (meta := XSMN_PROVINCE_MAP.get(r.province_code)) is not None
                and draw_day in meta.draw_days
            ]

        if search_number is not None:
            if match_mode == "exact":
                results = [r for r in results if search_number in r.prizes.all_numbers()]
            else:
                results = [
                    r
                    for r in results
                    if any(num.endswith(search_number) for num in r.prizes.all_numbers())
                ]

        return results

    return _run_with_connection(conn, db_path, _op)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def delete_result_by_province(
    province_code: str,
    *,
    validate_code: bool = True,
    db_path: str | Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> bool:
    """Delete a single province's row. Returns True if a row was deleted."""
    code = normalize_province_code(province_code, validate=validate_code)

    def _op(c: sqlite3.Connection) -> bool:
        with c:
            cursor = c.execute(
                "DELETE FROM latest_lottery_results WHERE province_code = ?",
                (code,),
            )
            return cursor.rowcount > 0

    return _run_with_connection(conn, db_path, _op)


def delete_results_by_date(
    draw_date: str,
    *,
    db_path: str | Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Delete all rows matching `draw_date` (YYYY-MM-DD). Returns deleted row count."""
    validated_date = validate_draw_date(draw_date)

    def _op(c: sqlite3.Connection) -> int:
        with c:
            cursor = c.execute(
                "DELETE FROM latest_lottery_results WHERE draw_date = ?",
                (validated_date,),
            )
            return cursor.rowcount

    return _run_with_connection(conn, db_path, _op)


def clear_all_results(
    *,
    db_path: str | Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Delete all rows from `latest_lottery_results`. Returns deleted row count."""

    def _op(c: sqlite3.Connection) -> int:
        with c:
            cursor = c.execute("DELETE FROM latest_lottery_results")
            return cursor.rowcount

    return _run_with_connection(conn, db_path, _op)
