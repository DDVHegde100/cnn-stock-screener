"""Shared parsing helpers."""

from __future__ import annotations

import math
import re


def scale_annual_to_months(annual_pct: float, months: float) -> float:
    return annual_pct * math.sqrt(months / 12.0)


def strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).replace("&amp;", "&").strip()


def parse_number(value: str | None) -> float | None:
    if value is None or value in {"", "-"}:
        return None
    cleaned = str(value).replace("%", "").replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_percent(value: str | None) -> float | None:
    num = parse_number(value)
    return num
