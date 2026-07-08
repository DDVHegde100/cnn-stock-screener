#!/usr/bin/env python3
"""Export Google Sheets CSVs from latest_scan.json including ASR fields."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from screener.portfolio import PortfolioLine
from screener.report import write_csv_reports
from screener.scanner import ScanResult
from screener.scoring import ScoredStock


def load_result(path: Path) -> ScanResult:
    data = json.loads(path.read_text())
    return ScanResult(
        scanned_at=data["scanned_at"],
        duration_sec=data["duration_sec"],
        universe_size=data["universe_size"],
        fetched_count=data["fetched_count"],
        qualified_count=data["qualified_count"],
        top_picks=[ScoredStock(**p) for p in data["top_picks"]],
        portfolio=[PortfolioLine(**p) for p in data["portfolio"]],
        portfolio_summary=data["portfolio_summary"],
        errors=data.get("errors", 0),
    )


def main() -> int:
    scan_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/latest_scan.json")
    out_dir = Path("output/sheets")
    result = load_result(scan_path)
    paths = write_csv_reports(result, out_dir)
    print(f"Exported from {scan_path}:")
    for label, path in paths.items():
        print(f"  {label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
