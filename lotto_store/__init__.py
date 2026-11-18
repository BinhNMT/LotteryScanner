"""Python interfaces for Read, Write, Query, and Delete on XSMN latest-state SQLite store."""

from .db import DEFAULT_DB_PATH, DEFAULT_SCHEMA_PATH, lottery_db_session, open_lottery_db
from .models import LatestLotteryResult, LotterySyncInput, PRIZE_SPEC, XsmnPrizes, validate_draw_date
from .operations import (
    clear_all_results,
    count_results,
    delete_result_by_province,
    delete_results_by_date,
    get_all_results,
    get_result_by_province,
    query_results,
    sync_results,
    upsert_result,
)
from .provinces import (
    XSMN_PROVINCES,
    XSMN_PROVINCE_MAP,
    XsmnProvinceMeta,
    normalize_province_code,
)

__all__ = [
    # DB / session
    "DEFAULT_DB_PATH",
    "DEFAULT_SCHEMA_PATH",
    "open_lottery_db",
    "lottery_db_session",
    # Models & validation
    "PRIZE_SPEC",
    "XsmnPrizes",
    "LotterySyncInput",
    "LatestLotteryResult",
    "validate_draw_date",
    # Provinces
    "XsmnProvinceMeta",
    "XSMN_PROVINCES",
    "XSMN_PROVINCE_MAP",
    "normalize_province_code",
    # Write
    "sync_results",
    "upsert_result",
    # Read
    "get_all_results",
    "get_result_by_province",
    # Query
    "count_results",
    "query_results",
    # Delete
    "delete_result_by_province",
    "delete_results_by_date",
    "clear_all_results",
]
