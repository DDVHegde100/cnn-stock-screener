"""Load and filter US equity tickers from NASDAQ symbol directories."""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path

NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

EXCLUDE_NAME_FRAGMENTS = (
    " warrant",
    " warrants",
    " rights",
    " unit",
    " units",
    " preferred",
    " notes due",
    " debenture",
    " depositary",
    " acquisition corp",
    " spac",
    " blank check",
)

# NYSE/NASDAQ/other exchange codes we keep (skip when not on a major equity venue)
VALID_EXCHANGES = {"N", "A", "P", "Z", "V"}


@dataclass(frozen=True)
class TickerInfo:
    symbol: str
    name: str
    exchange: str


def _fetch_lines(url: str) -> list[str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace").strip().splitlines()


def _is_common_equity(symbol: str, name: str, *, etf: str, test_issue: str) -> bool:
    if test_issue == "Y" or etf == "Y":
        return False
    if not symbol or symbol.startswith("File Creation"):
        return False
    if not re.fullmatch(r"[A-Z][A-Z0-9.]{0,9}", symbol):
        return False

    lower_name = name.lower()
    if any(fragment in lower_name for fragment in EXCLUDE_NAME_FRAGMENTS):
        return False

    # Skip obvious derivative tickers (5+ chars ending in W/R/U)
    if len(symbol) >= 5 and symbol[-1] in {"W", "R", "U"}:
        return False

    return True


def save_ticker_manifest(tickers: list[TickerInfo], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {t.symbol: {"name": t.name, "exchange": t.exchange} for t in tickers}
    path.write_text(json.dumps(data, indent=2))


def load_ticker_manifest(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _cache_has_forecast(row: dict | None) -> dict | None:
    if row is None:
        return None
    if "forecast" in row:
        return row["forecast"]
    if any(k in row for k in ("current_stock_price", "current_price", "median_target")):
        return row
    return None


def load_tickers_from_cache(cache: dict[str, dict], manifest: dict[str, dict] | None = None) -> list[TickerInfo]:
    """Build ticker list from cached forecast keys — no network."""
    manifest = manifest or {}
    tickers = []
    for symbol, row in sorted(cache.items()):
        fc = _cache_has_forecast(row)
        if fc is None:
            continue
        sym = fc.get("symbol", symbol)
        meta = manifest.get(sym, {})
        tickers.append(TickerInfo(
            symbol=sym,
            name=meta.get("name") or sym,
            exchange=meta.get("exchange", ""),
        ))
    return tickers


def load_all_tickers(*, offline_cache: dict[str, dict] | None = None, manifest: dict[str, dict] | None = None) -> list[TickerInfo]:
    """Return deduplicated common-stock tickers sorted alphabetically."""
    if offline_cache is not None:
        return load_tickers_from_cache(offline_cache, manifest)
    seen: set[str] = set()
    tickers: list[TickerInfo] = []

    nasdaq_lines = _fetch_lines(NASDAQ_URL)
    for line in nasdaq_lines[1:]:
        if line.startswith("File Creation"):
            break
        parts = line.split("|")
        if len(parts) < 8:
            continue
        symbol, name, _category, test_issue, _fin, _lot, etf, _next = parts[:8]
        if not _is_common_equity(symbol, name, etf=etf, test_issue=test_issue):
            continue
        if symbol not in seen:
            seen.add(symbol)
            tickers.append(TickerInfo(symbol=symbol, name=name, exchange="NASDAQ"))

    other_lines = _fetch_lines(OTHER_URL)
    for line in other_lines[1:]:
        if line.startswith("File Creation"):
            break
        parts = line.split("|")
        if len(parts) < 8:
            continue
        symbol, name, exchange, _cqs, etf, _lot, test_issue, _nasdaq = parts[:8]
        if exchange not in VALID_EXCHANGES:
            continue
        if not _is_common_equity(symbol, name, etf=etf, test_issue=test_issue):
            continue
        if symbol not in seen:
            seen.add(symbol)
            tickers.append(TickerInfo(symbol=symbol, name=name, exchange=exchange))

    tickers.sort(key=lambda t: t.symbol)
    return tickers
