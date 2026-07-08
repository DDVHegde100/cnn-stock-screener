"""Orchestrate full-universe CNN forecast scan with caching."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .cnn import CnnAnalystRatings, CnnForecast, fetch_analyst_ratings, fetch_forecast
from .finviz import FinvizForecast, fetch_finviz_forecast
from .portfolio import build_portfolio
from .scoring import ScoredStock, rank_stocks, score_forecast
from .tickers import TickerInfo, load_all_tickers, load_ticker_manifest, save_ticker_manifest

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None


@dataclass
class ScanConfig:
    budget: float = 10_000.0
    top_n: int = 30
    horizon_months: float = 6.0
    min_price: float = 5.0
    min_median_upside_1y: float = 15.0
    max_median_upside_1y: float = 80.0
    max_downside_1y: float = 15.0
    min_analysts: int = 15
    min_asr: float = 65.0
    min_source_agreement: float = 60.0
    workers: int = 8
    request_delay_ms: int = 120
    limit: int | None = None
    cache_only: bool = False
    cache_path: Path | None = None


@dataclass
class ScanResult:
    scanned_at: str
    duration_sec: float
    universe_size: int
    fetched_count: int
    qualified_count: int
    top_picks: list[ScoredStock]
    portfolio: list
    portfolio_summary: dict
    errors: int

    def to_dict(self) -> dict:
        return {
            "scanned_at": self.scanned_at,
            "duration_sec": self.duration_sec,
            "universe_size": self.universe_size,
            "fetched_count": self.fetched_count,
            "qualified_count": self.qualified_count,
            "top_picks": [p.to_dict() for p in self.top_picks],
            "portfolio": [p.to_dict() for p in self.portfolio],
            "portfolio_summary": self.portfolio_summary,
            "errors": self.errors,
        }


def _load_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(path: Path, cache: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2))


def _normalize_cache_entry(row: dict | None) -> dict | None:
    if row is None:
        return None
    if "forecast" in row:
        return {
            "forecast": row["forecast"],
            "ratings": row.get("ratings"),
            "finviz": row.get("finviz"),
        }
    if any(k in row for k in ("current_stock_price", "current_price", "median_target")):
        return {"forecast": row, "ratings": row.get("ratings"), "finviz": row.get("finviz")}
    return None


def _entry_forecast(entry: dict) -> CnnForecast | None:
    fc = entry.get("forecast")
    if not fc:
        return None
    if "current_price" in fc:
        return CnnForecast(**fc)
    return CnnForecast.from_api_row(fc)


def _entry_ratings(entry: dict) -> CnnAnalystRatings | None:
    rt = entry.get("ratings")
    if not rt:
        return None
    return CnnAnalystRatings(**rt)


def _entry_finviz(entry: dict) -> FinvizForecast | None:
    fv = entry.get("finviz")
    if not fv:
        return None
    return FinvizForecast(**fv)


def _score_entry(ticker: TickerInfo, entry: dict, config: ScanConfig) -> ScoredStock | None:
    forecast = _entry_forecast(entry)
    if forecast is None:
        return None
    return score_forecast(
        forecast,
        ratings=_entry_ratings(entry),
        finviz=_entry_finviz(entry),
        name=ticker.name,
        exchange=ticker.exchange,
        horizon_months=config.horizon_months,
        min_price=config.min_price,
        min_median_upside_1y=config.min_median_upside_1y,
        max_median_upside_1y=config.max_median_upside_1y,
        max_downside_1y=config.max_downside_1y,
        min_analysts=config.min_analysts,
        min_asr=config.min_asr,
        min_source_agreement=config.min_source_agreement,
    )


def _process_ticker(ticker: TickerInfo, config: ScanConfig) -> tuple[str, dict | None, ScoredStock | None]:
    forecast = fetch_forecast(ticker.symbol)
    if forecast is None:
        return ticker.symbol, None, None

    ratings = fetch_analyst_ratings(ticker.symbol)
    finviz = fetch_finviz_forecast(ticker.symbol)
    entry = {
        "forecast": asdict(forecast),
        "ratings": asdict(ratings) if ratings else None,
        "finviz": asdict(finviz) if finviz else None,
    }
    scored = _score_entry(ticker, entry, config)
    return ticker.symbol, entry, scored


def _backfill_entry(ticker: TickerInfo, entry: dict) -> dict:
    if not entry.get("ratings"):
        ratings = fetch_analyst_ratings(ticker.symbol)
        entry = {**entry, "ratings": asdict(ratings) if ratings else None}
    if not entry.get("finviz"):
        finviz = fetch_finviz_forecast(ticker.symbol)
        entry = {**entry, "finviz": asdict(finviz) if finviz else None}
    return entry


def _needs_backfill(entry: dict) -> bool:
    return not entry.get("ratings") or not entry.get("finviz")


def run_scan(config: ScanConfig, on_progress=None) -> ScanResult:
    start = time.time()
    cache_path = config.cache_path or Path("output/forecast_cache.json")
    cache = _load_cache(cache_path)

    if config.cache_only:
        manifest_path = (config.cache_path or Path("output/forecast_cache.json")).parent / "ticker_manifest.json"
        manifest = load_ticker_manifest(manifest_path)
        tickers = load_all_tickers(offline_cache=cache, manifest=manifest)
    else:
        tickers = load_all_tickers()
        manifest_path = (config.cache_path or Path("output/forecast_cache.json")).parent / "ticker_manifest.json"
        save_ticker_manifest(tickers, manifest_path)
    if config.limit:
        tickers = tickers[: config.limit]

    universe_size = len(tickers)
    to_fetch = [] if config.cache_only else [t for t in tickers if t.symbol not in cache]
    cached_hits = [t for t in tickers if t.symbol in cache]

    scored: list[ScoredStock] = []
    errors = 0
    fetched_count = len(cached_hits)

    needs_backfill = []
    for ticker in cached_hits:
        entry = _normalize_cache_entry(cache.get(ticker.symbol))
        if entry and _needs_backfill(entry):
            needs_backfill.append(ticker)

    for ticker in cached_hits:
        entry = _normalize_cache_entry(cache.get(ticker.symbol))
        if entry is None:
            continue
        cache[ticker.symbol] = entry

    if needs_backfill:
        with ThreadPoolExecutor(max_workers=config.workers) as pool:
            futures = {pool.submit(_backfill_entry, t, cache[t.symbol]): t for t in needs_backfill}
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    cache[ticker.symbol] = future.result()
                except Exception:
                    errors += 1
        _save_cache(cache_path, cache)

    for ticker in cached_hits:
        entry = _normalize_cache_entry(cache.get(ticker.symbol))
        if entry is None:
            continue
        hit = _score_entry(ticker, entry, config)
        if hit:
            scored.append(hit)

    delay_sec = config.request_delay_ms / 1000.0
    iterator = to_fetch
    progress = None
    if tqdm and on_progress is None:
        progress = tqdm(iterator, desc="Scanning tickers", unit="stk")
        iterator = progress

    with ThreadPoolExecutor(max_workers=config.workers) as pool:
        futures = {pool.submit(_process_ticker, ticker, config): ticker for ticker in to_fetch}

        for i, future in enumerate(as_completed(futures), start=1):
            ticker = futures[future]
            try:
                symbol, row, hit = future.result()
                cache[symbol] = row
                fetched_count += 1
                if hit:
                    scored.append(hit)
            except Exception:
                errors += 1
                cache[ticker.symbol] = None

            if i % 25 == 0:
                _save_cache(cache_path, cache)

            if on_progress:
                on_progress(i, len(to_fetch), ticker.symbol)
            elif progress:
                progress.set_postfix(qualified=len(scored), refresh=False)

            if delay_sec > 0:
                time.sleep(delay_sec / config.workers)

    if progress:
        progress.close()

    _save_cache(cache_path, cache)

    top_picks = rank_stocks(scored, config.top_n)
    portfolio, summary = build_portfolio(top_picks, config.budget, min_positions=config.top_n)

    return ScanResult(
        scanned_at=datetime.now(timezone.utc).isoformat(),
        duration_sec=round(time.time() - start, 1),
        universe_size=universe_size,
        fetched_count=fetched_count,
        qualified_count=len(scored),
        top_picks=top_picks,
        portfolio=portfolio,
        portfolio_summary=summary,
        errors=errors,
    )
