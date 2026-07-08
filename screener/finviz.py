"""Fetch Finviz analyst target and recommendation data."""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from .utils import parse_number, strip_html

FINVIZ_QUOTE_URL = "https://finviz.com/quote.ashx?t={symbol}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


@dataclass
class FinvizForecast:
    symbol: str
    price: float | None
    target_price: float | None
    upside_pct: float | None
    recommendation: float | None  # 1=Strong Buy … 5=Strong Sell
    source: str = "finviz"

    @property
    def sentiment_score(self) -> float | None:
        """Map Finviz 1–5 recommendation to 0–100 bullish score."""
        if self.recommendation is None:
            return None
        return max(0.0, min(100.0, (5.0 - self.recommendation) / 4.0 * 100.0))


def fetch_finviz_forecast(symbol: str) -> FinvizForecast | None:
    url = FINVIZ_QUOTE_URL.format(symbol=symbol)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None

    cells = re.findall(r'<td[^>]*class="[^"]*snapshot-td2[^"]*"[^>]*>(.*?)</td>', html, re.S)
    texts = [strip_html(c) for c in cells]
    metrics: dict[str, str] = {}
    for i in range(0, len(texts) - 1, 2):
        key = texts[i].rstrip(".")
        metrics[key] = texts[i + 1]

    price = parse_number(metrics.get("Price")) or parse_number(metrics.get("Prev Close"))
    target = parse_number(metrics.get("Target Price"))
    recom = parse_number(metrics.get("Recom"))

    upside = None
    if price and target and price > 0:
        upside = ((target - price) / price) * 100.0

    if target is None and recom is None:
        return None

    return FinvizForecast(
        symbol=symbol,
        price=price,
        target_price=target,
        upside_pct=round(upside, 2) if upside is not None else None,
        recommendation=recom,
    )
