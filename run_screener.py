#!/usr/bin/env python3
"""Scan US stocks using multi-source analyst forecasts and build a portfolio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from screener.report import write_csv_reports, write_html_report, write_json_report
from screener.scanner import ScanConfig, run_scan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-source analyst screener with proprietary ASR rating."
    )
    parser.add_argument("--budget", type=float, default=10_000.0, help="Investment budget in USD (default: 10000)")
    parser.add_argument("--top", type=int, default=30, help="Number of top picks (default: 30)")
    parser.add_argument("--months", type=float, default=6.0, help="Investment horizon in months (default: 6)")
    parser.add_argument("--min-upside", type=float, default=15.0, help="Min 1Y median analyst upside %% (default: 15)")
    parser.add_argument("--max-upside", type=float, default=80.0, help="Max 1Y median upside %% (default: 80)")
    parser.add_argument("--max-downside", type=float, default=15.0, help="Max 1Y analyst downside on low target (default: 15)")
    parser.add_argument("--min-analysts", type=int, default=15, help="Min CNN analyst ratings count (default: 15)")
    parser.add_argument("--min-asr", type=float, default=65.0, help="Min proprietary ASR score 0-100 (default: 65)")
    parser.add_argument("--min-agreement", type=float, default=60.0, help="Min CNN/Finviz agreement %% (default: 60)")
    parser.add_argument("--min-price", type=float, default=5.0, help="Minimum stock price (default: 5)")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers (default: 8)")
    parser.add_argument("--delay-ms", type=int, default=120, help="Delay between requests in ms (default: 120)")
    parser.add_argument("--limit", type=int, default=None, help="Limit tickers scanned (for testing)")
    parser.add_argument("--from-cache", action="store_true", help="Rescore cached data; backfills missing sources")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory (default: output)")
    return parser.parse_args()


def print_portfolio(result) -> None:
    print("\n" + "=" * 80)
    print("  MULTI-SOURCE ANALYST SCREENER — ASR RATED PORTFOLIO")
    print("=" * 80)
    print(f"  Universe scanned : {result.universe_size:,}")
    print(f"  With data        : {result.fetched_count:,}")
    print(f"  Qualified        : {result.qualified_count:,}")
    print(f"  Duration         : {result.duration_sec}s")
    print("-" * 80)

    s = result.portfolio_summary
    print(f"  Budget           : ${s['budget']:,.2f}")
    print(f"  Invested         : ${s['invested']:,.2f}")
    print(f"  Cash remaining   : ${s['cash_remaining']:,.2f}")
    print(f"  Expected 6M gain : +{s['expected_6m_return_pct']:.1f}% (${s['expected_6m_profit_usd']:,.2f})")
    print("-" * 80)
    print(f"  {'#':<3} {'Ticker':<8} {'ASR':>6} {'Grade':>5} {'Agree':>6} {'Invest':>10} {'6M':>7}")
    print("-" * 80)

    picks = {p.symbol: p for p in result.top_picks}
    for line in result.portfolio:
        p = picks.get(line.symbol)
        print(
            f"  {line.rank:<3} {line.symbol:<8} {line.composite_score:>6.1f} "
            f"{(p.asr_grade if p else '-'):>5} "
            f"{(p.source_agreement_pct if p else 0):>5.0f}% "
            f"${line.actual_invested_usd:>8,.2f} +{line.expected_6m_gain_pct:>5.1f}%"
        )

    print("=" * 80)
    print("\nTop 10 — CNN vs Finviz consensus:")
    for i, p in enumerate(result.top_picks[:10], 1):
        fv = f"+{p.finviz_upside_pct:.1f}%" if p.finviz_upside_pct is not None else "n/a"
        print(
            f"  {i:2}. {p.symbol:<6} ASR {p.asr_score:.1f} ({p.asr_grade}) {p.asr_label:<14} "
            f"CNN +{p.pct_median_1y:.1f}%  FV {fv}  agree {p.source_agreement_pct:.0f}%"
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
        min_asr=args.min_asr,
        min_source_agreement=args.min_agreement,
        workers=args.workers,
        request_delay_ms=args.delay_ms,
        limit=args.limit,
        cache_only=args.from_cache,
        cache_path=out_dir / "forecast_cache.json",
    )

    print("Loading ticker universe...")
    if args.from_cache:
        print("Rescoring from cache (backfills Finviz/CNN ratings if missing)...")
    else:
        print(f"Scanning with {config.workers} workers...")

    result = run_scan(config)
    write_json_report(result, out_dir / "latest_scan.json")
    write_html_report(result, out_dir / "portfolio_report.html")
    csv_paths = write_csv_reports(result, out_dir / "sheets")

    print_portfolio(result)
    print(f"JSON report : {out_dir / 'latest_scan.json'}")
    print(f"HTML report : {out_dir / 'portfolio_report.html'}")
    print("Google Sheets CSVs:")
    for label, path in csv_paths.items():
        print(f"  {label:12} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
