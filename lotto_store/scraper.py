"""Scraper and HTML parser for XSMN results from https://xsmn.mobi/."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html.parser import HTMLParser
import logging
from pathlib import Path
import re
import sys
import urllib.request
from typing import Sequence

from .db import DEFAULT_DB_PATH, DEFAULT_EXPORT_JSON_PATH, lottery_db_session
from .models import LotterySyncInput, XsmnPrizes
from .operations import export_results_to_json, get_all_results, sync_results
from .provinces import normalize_province_code

_UNSET = object()

logger = logging.getLogger(__name__)

DEFAULT_XSMN_URL = "https://xsmn.mobi/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_DATE_HREF_RE = re.compile(r"/xsmn-(\d{2})-(\d{2})-(\d{4})\.html")

_PCODE_ALIASES: dict[str, str] = {
    "hcm": "TPHCM",
    "tp": "TPHCM",
    "tphcm": "TPHCM",
}

_TIER_LABEL_MAP: dict[str, str] = {
    "G8": "giai8",
    "G7": "giai7",
    "G6": "giai6",
    "G5": "giai5",
    "G4": "giai4",
    "G3": "giai3",
    "G2": "giai2",
    "G1": "giai1",
    "ĐB": "dac_biet",
    "DB": "dac_biet",
}


def _map_pcode(raw_pcode: str) -> str:
    cleaned = raw_pcode.strip().lower()
    mapped = _PCODE_ALIASES.get(cleaned, cleaned.upper())
    return normalize_province_code(mapped)


def _has_class(attrs_dict: dict[str, str | None], class_name: str) -> bool:
    raw = attrs_dict.get("class") or ""
    return class_name in raw.split()


class _XsmnMobiParser(HTMLParser):
    """Stateful HTMLParser for `table.extendable.read-result` blocks on xsmn.mobi."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.raw_tables: list[tuple[str, list[str], list[list[list[str]]]]] = []

        self._current_date: str | None = None
        self._in_table = False
        self._in_thead = False
        self._in_tbody = False
        self._in_tr = False
        self._in_td = False
        self._in_div = False

        self._table_pcodes: list[str] = []
        self._table_rows: list[list[list[str]]] = []
        self._current_row: list[list[str]] = []
        self._current_cell_divs: list[str] = []
        self._current_cell_text: list[str] = []
        self._current_div_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)

        if tag == "a" and _has_class(attrs_dict, "vietlott-link"):
            href = attrs_dict.get("href") or ""
            match = _DATE_HREF_RE.search(href)
            if match:
                day, month, year = match.groups()
                self._current_date = f"{year}-{month}-{day}"
            return

        if tag == "table" and _has_class(attrs_dict, "extendable") and _has_class(attrs_dict, "read-result"):
            self._in_table = True
            self._table_pcodes = []
            self._table_rows = []
            return

        if not self._in_table:
            return

        if tag == "thead":
            self._in_thead = True
        elif tag == "tbody":
            self._in_tbody = True
        elif tag == "tr":
            self._in_tr = True
            self._current_row = []
        elif tag == "th" and self._in_thead and self._in_tr:
            pcode = attrs_dict.get("data-pcode")
            if pcode:
                self._table_pcodes.append(pcode)
        elif tag == "td" and self._in_tbody and self._in_tr:
            self._in_td = True
            self._current_cell_divs = []
            self._current_cell_text = []
        elif tag == "div" and self._in_td:
            self._in_div = True
            self._current_div_text = []

    def handle_endtag(self, tag: str) -> None:
        if not self._in_table:
            return

        if tag == "div" and self._in_div:
            self._in_div = False
            text = "".join(self._current_div_text).strip()
            if text:
                self._current_cell_divs.append(text)
        elif tag == "td" and self._in_td:
            self._in_td = False
            if self._current_cell_divs:
                self._current_row.append(self._current_cell_divs)
            else:
                text = "".join(self._current_cell_text).strip()
                self._current_row.append([text] if text else [])
        elif tag == "tr" and self._in_tr:
            self._in_tr = False
            if self._in_tbody and self._current_row:
                self._table_rows.append(self._current_row)
        elif tag == "tbody":
            self._in_tbody = False
        elif tag == "thead":
            self._in_thead = False
        elif tag == "table":
            self._in_table = False
            if self._current_date and self._table_pcodes and self._table_rows:
                self.raw_tables.append(
                    (self._current_date, self._table_pcodes, self._table_rows)
                )

    def handle_data(self, data: str) -> None:
        if self._in_div:
            self._current_div_text.append(data)
        elif self._in_td:
            self._current_cell_text.append(data)


@dataclass(frozen=True, slots=True)
class SyncSummary:
    """Summary returned by `sync_from_xsmn_mobi`."""

    parsed_count: int
    synced_count: int
    skipped_incomplete: tuple[str, ...]
    skipped_older: tuple[str, ...]
    results: tuple[LotterySyncInput, ...]
    export_json_path: Path | None = None


def fetch_xsmn_html(
    url: str = DEFAULT_XSMN_URL,
    *,
    timeout: float = 15.0,
) -> str:
    """Fetch HTML content from xsmn.mobi."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def parse_xsmn_mobi_html(
    html: str,
    *,
    deduplicate_latest: bool = True,
) -> tuple[list[LotterySyncInput], list[str]]:
    """Parse xsmn.mobi HTML into validated `LotterySyncInput` records.

    Returns:
        A tuple of `(records, skipped_incomplete)` where `skipped_incomplete`
        contains human-readable descriptions of provinces skipped due to
        incomplete or unparseable prize tiers (e.g., while a draw is live).
    """
    parser = _XsmnMobiParser()
    parser.feed(html)
    parser.close()

    parsed_records: list[LotterySyncInput] = []
    skipped_incomplete: list[str] = []

    for draw_date, raw_pcodes, rows in parser.raw_tables:
        province_codes: list[str] = []
        for raw_pcode in raw_pcodes:
            try:
                province_codes.append(_map_pcode(raw_pcode))
            except ValueError as exc:
                logger.warning("Skipping unknown province code %r on %s: %s", raw_pcode, draw_date, exc)
                province_codes.append("")

        per_province: dict[int, dict[str, list[str]]] = {
            idx: {} for idx, code in enumerate(province_codes) if code
        }

        for row in rows:
            if not row or not row[0]:
                continue
            tier_label = row[0][0].strip().upper()
            attr_name = _TIER_LABEL_MAP.get(tier_label)
            if not attr_name:
                continue

            for col_idx, cell_values in enumerate(row[1:]):
                if col_idx in per_province:
                    per_province[col_idx][attr_name] = cell_values

        for col_idx, tier_data in per_province.items():
            province_code = province_codes[col_idx]
            try:
                prizes = XsmnPrizes(**tier_data)
                parsed_records.append(
                    LotterySyncInput(
                        province_code=province_code,
                        draw_date=draw_date,
                        prizes=prizes,
                    )
                )
            except (TypeError, ValueError) as exc:
                msg = f"{province_code} ({draw_date}): {exc}"
                logger.warning("Skipping incomplete/invalid draw %s", msg)
                skipped_incomplete.append(msg)

    if not deduplicate_latest:
        return parsed_records, skipped_incomplete

    latest_by_province: dict[str, LotterySyncInput] = {}
    for record in parsed_records:
        existing = latest_by_province.get(record.province_code)
        if existing is None or record.draw_date > existing.draw_date:
            latest_by_province[record.province_code] = record

    return list(latest_by_province.values()), skipped_incomplete


def _resolve_export_path(
    db_path: str | Path | None,
    export_json_path: str | Path | None | object,
    *,
    dry_run: bool,
) -> Path | None:
    if dry_run:
        return None
    if export_json_path is _UNSET:
        if db_path is None:
            return DEFAULT_EXPORT_JSON_PATH
        if str(db_path) == ":memory:":
            return None
        return Path(db_path).with_suffix(".json")
    if export_json_path is None:
        return None
    return Path(export_json_path)


def sync_from_xsmn_mobi(
    *,
    url: str = DEFAULT_XSMN_URL,
    db_path: str | Path | None = None,
    timeout: float = 15.0,
    dry_run: bool = False,
    only_if_newer: bool = True,
    export_json_path: str | Path | None | object = _UNSET,
) -> SyncSummary:
    """Fetch results from xsmn.mobi, parse them, update SQLite, and export JSON."""
    html = fetch_xsmn_html(url, timeout=timeout)
    records, skipped_incomplete = parse_xsmn_mobi_html(html, deduplicate_latest=True)

    skipped_older: list[str] = []
    to_sync: list[LotterySyncInput] = records
    resolved_export = _resolve_export_path(db_path, export_json_path, dry_run=dry_run)
    exported_path: Path | None = None

    if only_if_newer and records:
        with lottery_db_session(db_path) as conn:
            existing_map = {
                row.province_code: row.draw_date for row in get_all_results(conn=conn)
            }
            filtered: list[LotterySyncInput] = []
            for item in records:
                existing_date = existing_map.get(item.province_code)
                if existing_date is not None and item.draw_date < existing_date:
                    skipped_older.append(
                        f"{item.province_code} (parsed {item.draw_date} < stored {existing_date})"
                    )
                else:
                    filtered.append(item)
            to_sync = filtered
            synced_count = 0 if dry_run else sync_results(to_sync, conn=conn)
            if not dry_run and resolved_export is not None:
                exported_path = export_results_to_json(resolved_export, conn=conn)
    elif not dry_run:
        with lottery_db_session(db_path) as conn:
            synced_count = sync_results(to_sync, conn=conn)
            if resolved_export is not None:
                exported_path = export_results_to_json(resolved_export, conn=conn)
    else:
        synced_count = 0

    return SyncSummary(
        parsed_count=len(records),
        synced_count=synced_count,
        skipped_incomplete=tuple(skipped_incomplete),
        skipped_older=tuple(skipped_older),
        results=tuple(to_sync),
        export_json_path=exported_path,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse XSMN lottery results from https://xsmn.mobi/ and update SQLite store."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_XSMN_URL,
        help=f"Source URL to fetch (default: {DEFAULT_XSMN_URL})",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite database path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP request timeout in seconds (default: 15.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate results without writing to the database.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite even if stored draw_date is newer than parsed draw_date.",
    )
    parser.add_argument(
        "--export-json",
        default=None,
        help="Path to export JSON snapshot after DB update (default: <db>.json or lottery_latest.json).",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Skip exporting JSON snapshot after DB update.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    export_arg: str | Path | None | object = (
        None if args.no_export else (args.export_json if args.export_json is not None else _UNSET)
    )

    summary = sync_from_xsmn_mobi(
        url=args.url,
        db_path=args.db,
        timeout=args.timeout,
        dry_run=args.dry_run,
        only_if_newer=not args.force,
        export_json_path=export_arg,
    )

    mode = "DRY-RUN" if args.dry_run else "SYNCED"
    print(
        f"[{mode}] Parsed {summary.parsed_count} province(s), "
        f"updated {summary.synced_count} record(s) in {args.db}."
    )
    if summary.export_json_path is not None:
        print(f"[EXPORTED] Static JSON snapshot written to {summary.export_json_path}.")
    for item in sorted(summary.results, key=lambda r: (r.draw_date, r.province_code), reverse=True):
        print(
            f"  - {item.province_code:<5} | {item.draw_date} | "
            f"G8={item.prizes.giai8[0]} | ĐB={item.prizes.dac_biet[0]}"
        )

    if summary.skipped_incomplete:
        print(f"Skipped {len(summary.skipped_incomplete)} incomplete draw(s):")
        for msg in summary.skipped_incomplete:
            print(f"  * {msg}")

    if summary.skipped_older:
        print(f"Skipped {len(summary.skipped_older)} older draw(s):")
        for msg in summary.skipped_older:
            print(f"  * {msg}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
