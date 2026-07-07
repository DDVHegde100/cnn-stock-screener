#!/usr/bin/env python3
"""Scan all US stocks using CNN analyst forecasts and build a portfolio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from screener.report import write_csv_reports, write_html_report, write_json_report
from screener.scanner import ScanConfig, run_scan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan every US stock ticker via CNN analyst forecasts and rank top buys."
    )
    parser.add_argument("--budget", type=float, default=10_000.0, help="Investment budget in USD (default: 10000)")
    parser.add_argument("--top", type=int, default=30, help="Number of top picks (default: 30)")
    parser.add_argument("--months", type=float, default=6.0, help="Investment horizon in months (default: 6)")
    parser.add_argument("--min-upside", type=float, default=15.0, help="Min 1Y median analyst upside %% (default: 15)")
    parser.add_argument("--max-upside", type=float, default=80.0, help="Max 1Y median upside %% — filters outliers (default: 80)")
    parser.add_argument("--max-downside", type=float, default=15.0, help="Max 1Y analyst downside on low target (default: 15)")
    parser.add_argument("--min-analysts", type=int, default=15, help="Min CNN analyst ratings count (default: 15)")
    parser.add_argument("--min-price", type=float, default=5.0, help="Minimum stock price (default: 5)")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers (default: 8)")
    parser.add_argument("--delay-ms", type=int, default=120, help="Delay between requests in ms (default: 120)")
    parser.add_argument("--limit", type=int, default=None, help="Limit tickers scanned (for testing)")
    parser.add_argument("--from-cache", action="store_true", help="Rescore cached data only — no network calls")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory (default: output)")
    return parser.parse_args()


def print_portfolio(result) -> None:
    print("\n" + "=" * 72)
    print("  CNN ANALYST STOCK SCREENER — TOP PICKS & PORTFOLIO")
    print("=" * 72)
    print(f"  Universe scanned : {result.universe_size:,}")
    print(f"  With CNN data    : {result.fetched_count:,}")
    print(f"  Qualified        : {result.qualified_count:,}")
    print(f"  Duration         : {result.duration_sec}s")
    print("-" * 72)

    s = result.portfolio_summary
    print(f"  Budget           : ${s['budget']:,.2f}")
    print(f"  Invested         : ${s['invested']:,.2f}")
    print(f"  Cash remaining   : ${s['cash_remaining']:,.2f}")
    print(f"  Expected 6M gain : +{s['expected_6m_return_pct']:.1f}% (${s['expected_6m_profit_usd']:,.2f})")
    print("-" * 72)
    print(f"  {'#':<3} {'Ticker':<8} {'Weight':>7} {'Shares':>7} {'Invest':>10} {'6M Gain':>8} {'Score':>7}")
    print("-" * 72)

    for line in result.portfolio:
        print(
            f"  {line.rank:<3} {line.symbol:<8} {line.weight_pct:>6.1f}% "
            f"{line.shares:>7} ${line.actual_invested_usd:>8,.2f} "
            f"+{line.expected_6m_gain_pct:>6.1f}% {line.composite_score:>7.1f}"
        )

    print("=" * 72)
    print("\nTop 10 detail (CNN 1Y median / low / 6M estimate):")
    for i, p in enumerate(result.top_picks[:10], 1):
        print(
            f"  {i:2}. {p.symbol:<6}  price ${p.current_price:>8.2f}  "
            f"median +{p.pct_median_1y:>5.1f}%  low {p.pct_low_1y:>+6.1f}%  "
            f"6M est +{p.gain_6m_median_pct:.1f}%  ratio {p.upside_risk_ratio:.2f}"
        )
    print()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)

    config = ScanConfig(
        budget=args.budget,
        top_n=args.top,
        horizon_months=args.months,
        min_price=args.min_price,
        min_median_upside_1y=args.min_upside,
        max_median_upside_1y=args.max_upside,
        max_downside_1y=args.max_downside,
        min_analysts=args.min_analysts,
        workers=args.workers,
        request_delay_ms=args.delay_ms,
        limit=args.limit,
        cache_only=args.from_cache,
        cache_path=out_dir / "forecast_cache.json",
    )

    print("Loading ticker universe from NASDAQ...")
    if args.from_cache:
        print("Lightweight mode: rescoring from cache only (no API calls)...")
    else:
        print(f"Scanning with {config.workers} workers (cached results are reused)...")

    result = run_scan(config)
    write_json_report(result, out_dir / "latest_scan.json")
    write_html_report(result, out_dir / "portfolio_report.html")
    csv_paths = write_csv_reports(result, out_dir / "sheets")

    print_portfolio(result)
    print(f"JSON report : {out_dir / 'latest_scan.json'}")
    print(f"HTML report : {out_dir / 'portfolio_report.html'}")
    print(f"Cache file  : {out_dir / 'forecast_cache.json'}")
    print("Google Sheets CSVs (import each as a tab):")
    for label, path in csv_paths.items():
        print(f"  {label:12} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
