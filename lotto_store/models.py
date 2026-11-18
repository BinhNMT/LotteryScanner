"""Typed data models and validation helpers for the XSMN latest-state store."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import re
from typing import Any, Mapping, Sequence

from .provinces import normalize_province_code

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# (json_key, python_attr, expected_count, expected_digits)
PRIZE_SPEC: tuple[tuple[str, str, int, int], ...] = (
    ("giai8", "giai8", 1, 2),
    ("giai7", "giai7", 1, 3),
    ("giai6", "giai6", 3, 4),
    ("giai5", "giai5", 1, 4),
    ("giai4", "giai4", 7, 5),
    ("giai3", "giai3", 2, 5),
    ("giai2", "giai2", 1, 5),
    ("giai1", "giai1", 1, 5),
    ("dacBiet", "dac_biet", 1, 6),
)


def validate_draw_date(draw_date: str) -> str:
    """Validate YYYY-MM-DD format and calendar validity."""
    if not isinstance(draw_date, str) or not _DATE_PATTERN.match(draw_date):
        raise ValueError(f"draw_date must be in YYYY-MM-DD format, got {draw_date!r}")
    date.fromisoformat(draw_date)
    return draw_date


def _validate_prize_tier(
    tier_name: str,
    values: Sequence[str],
    expected_count: int,
    expected_digits: int,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError(f"{tier_name} must be a sequence of {expected_count} string(s).")
    if len(values) != expected_count:
        raise ValueError(
            f"{tier_name} must contain exactly {expected_count} value(s), got {len(values)}."
        )

    validated: list[str] = []
    for idx, val in enumerate(values):
        if not isinstance(val, str):
            raise TypeError(
                f"{tier_name}[{idx}] must be str to preserve leading zeros, got {type(val).__name__}."
            )
        if len(val) != expected_digits or not val.isdigit():
            raise ValueError(
                f"{tier_name}[{idx}] must be a {expected_digits}-digit string, got {val!r}."
            )
        validated.append(val)
    return tuple(validated)


@dataclass(frozen=True, slots=True)
class XsmnPrizes:
    """Prize tiers for XSMN (Giải 8 -> Giải Đặc Biệt).

    All numbers are stored as zero-padded strings (e.g. "05", "004192").
    """

    giai8: tuple[str, ...]
    giai7: tuple[str, ...]
    giai6: tuple[str, ...]
    giai5: tuple[str, ...]
    giai4: tuple[str, ...]
    giai3: tuple[str, ...]
    giai2: tuple[str, ...]
    giai1: tuple[str, ...]
    dac_biet: tuple[str, ...]

    def __post_init__(self) -> None:
        for json_key, attr, expected_count, expected_digits in PRIZE_SPEC:
            raw = getattr(self, attr)
            normalized = _validate_prize_tier(json_key, raw, expected_count, expected_digits)
            object.__setattr__(self, attr, normalized)

    def all_numbers(self) -> tuple[str, ...]:
        """Return a flat tuple of all winning numbers across all tiers."""
        numbers: list[str] = []
        for _, attr, _, _ in PRIZE_SPEC:
            numbers.extend(getattr(self, attr))
        return tuple(numbers)

    def to_dict(self) -> dict[str, list[str]]:
        """Serialize to the canonical JSON dictionary (with 'dacBiet' key)."""
        return {
            json_key: list(getattr(self, attr))
            for json_key, attr, _, _ in PRIZE_SPEC
        }

    def to_json(self) -> str:
        """Serialize to compact JSON string for SQLite storage."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> XsmnPrizes:
        """Construct XsmnPrizes from a dict (supports both 'dacBiet' and 'dac_biet')."""
        kwargs: dict[str, Any] = {}
        for json_key, attr, _, _ in PRIZE_SPEC:
            if json_key in data:
                kwargs[attr] = data[json_key]
            elif attr in data:
                kwargs[attr] = data[attr]
            else:
                raise ValueError(f"Missing required prize tier: {json_key!r}")
        return cls(**kwargs)

    @classmethod
    def from_json(cls, raw_json: str) -> XsmnPrizes:
        """Parse XsmnPrizes from a JSON string stored in SQLite."""
        parsed = json.loads(raw_json)
        if not isinstance(parsed, Mapping):
            raise ValueError("Prizes JSON must decode to an object.")
        return cls.from_dict(parsed)


@dataclass(frozen=True, slots=True)
class LotterySyncInput:
    """Input payload for writing/overwriting a province's latest draw result."""

    province_code: str
    draw_date: str
    prizes: XsmnPrizes

    def __post_init__(self) -> None:
        object.__setattr__(self, "province_code", normalize_province_code(self.province_code))
        object.__setattr__(self, "draw_date", validate_draw_date(self.draw_date))
        if isinstance(self.prizes, Mapping):
            object.__setattr__(self, "prizes", XsmnPrizes.from_dict(self.prizes))
        elif not isinstance(self.prizes, XsmnPrizes):
            raise TypeError(
                f"prizes must be XsmnPrizes or Mapping, got {type(self.prizes).__name__}."
            )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LotterySyncInput:
        """Build LotterySyncInput from snake_case or camelCase dict keys."""
        province_code = data.get("province_code") or data.get("provinceCode")
        draw_date = data.get("draw_date") or data.get("drawDate")
        prizes = data.get("prizes")
        if province_code is None or draw_date is None or prizes is None:
            raise ValueError("LotterySyncInput requires province_code, draw_date, and prizes.")
        return cls(province_code=province_code, draw_date=draw_date, prizes=prizes)


@dataclass(frozen=True, slots=True)
class LatestLotteryResult:
    """Domain representation of a row in `latest_lottery_results`."""

    province_code: str
    draw_date: str
    prizes: XsmnPrizes
    updated_at: str

    @classmethod
    def from_row(cls, row: Mapping[str, Any] | Sequence[Any]) -> LatestLotteryResult:
        """Map a SQLite row (sqlite3.Row or 4-tuple) to LatestLotteryResult."""
        if isinstance(row, Mapping) or hasattr(row, "keys"):
            return cls(
                province_code=row["province_code"],
                draw_date=row["draw_date"],
                prizes=XsmnPrizes.from_json(row["prizes"]),
                updated_at=row["updated_at"],
            )
        province_code, draw_date, prizes_json, updated_at = row
        return cls(
            province_code=province_code,
            draw_date=draw_date,
            prizes=XsmnPrizes.from_json(prizes_json),
            updated_at=updated_at,
        )
