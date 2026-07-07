# CNN Stock Screener

Batch scanner for US equities using CNN Markets analyst price targets. Ranks tickers by upside vs downside and outputs a score-weighted portfolio allocation.

## Stack

- Python 3.10+ (stdlib + optional `tqdm`)
- CNN Dataviz forecast API: `production.dataviz.cnn.io/quote/forecast/{symbol}`
- NASDAQ symbol directories for ticker universe (~5.4k common stocks)

## Usage

```bash
pip install -r requirements.txt   # optional progress bar
python3 run_screener.py
```

```bash
python3 run_screener.py --budget 10000 --top 30 --months 6
python3 run_screener.py --min-upside 15 --max-downside 15 --limit 500
```

## Pipeline

1. **Universe** — load NASDAQ/NYSE/AMEX symbols, filter ETFs/warrants/test issues
2. **Fetch** — pull median/high/low 1Y targets per ticker (parallel, cached)
3. **Score** — filter + rank on 6M scaled upside, downside floor, analyst spread
4. **Allocate** — score-weighted `$` split with per-position cap

## Filters (defaults)

| Param | Default |
|-------|---------|
| Min 1Y median upside | 15% |
| Max 1Y median upside | 80% |
| Max 1Y low-target downside | 15% |
| Min price | $5 |

6-month estimates use √time scaling from 12-month analyst targets.

## Output

```
output/
  portfolio_report.html   # dashboard
  latest_scan.json        # full results
  forecast_cache.json     # resume cache
```

First full scan ~2–5 min with cache warm; cold start longer depending on workers/delay.

## Layout

```
screener/
  tickers.py    # symbol universe
  cnn.py        # forecast API client
  scoring.py    # filter + rank
  portfolio.py  # dollar allocation
  scanner.py    # orchestration + cache
  report.py     # html/json export
run_screener.py
```

## Disclaimer

Research tool only — not financial advice. Analyst targets are estimates.
