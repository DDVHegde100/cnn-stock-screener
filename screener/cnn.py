"""Fetch CNN Markets analyst price forecasts."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

CNN_FORECAST_URL = "https://production.dataviz.cnn.io/quote/forecast/{symbol}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.cnn.com",
    "Referer": "https://www.cnn.com/markets/stocks/",
}


@dataclass
class CnnForecast:
    symbol: str
    current_price: float
    high_target: float
    median_target: float
    low_target: float
    pct_high: float
    pct_median: float
    pct_low: float
    last_updated: str | None

    @classmethod
    def from_api_row(cls, row: dict[str, Any]) -> "CnnForecast":
        return cls(
            symbol=row["symbol"],
            current_price=float(row["current_stock_price"]),
            high_target=float(row["high_target_price"]),
            median_target=float(row["median_target_price"]),
            low_target=float(row["low_target_price"]),
            pct_high=float(row["percent_high_price"]),
            pct_median=float(row["percent_median_price"]),
            pct_low=float(row["percent_low_price"]),
            last_updated=row.get("last_updated"),
        )


def fetch_forecast(symbol: str, *, retries: int = 2, retry_delay: float = 0.5) -> CnnForecast | None:
    url = CNN_FORECAST_URL.format(symbol=symbol)
    req = urllib.request.Request(
        url,
        headers={**HEADERS, "Referer": f"https://www.cnn.com/markets/stocks/{symbol}"},
    )

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read())
            row = payload[0] if isinstance(payload, list) else payload
            if not row:
                return None
            return CnnForecast.from_api_row(row)
        except urllib.error.HTTPError as err:
            if err.code in {404, 400}:
                return None
            if attempt < retries:
                time.sleep(retry_delay * (attempt + 1))
                continue
            return None
        except (urllib.error.URLError, TimeoutError, KeyError, TypeError, ValueError):
            if attempt < retries:
                time.sleep(retry_delay * (attempt + 1))
                continue
            return None

    return None
