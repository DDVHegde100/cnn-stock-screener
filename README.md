# Multi-Source Analyst Stock Screener

Batch scanner for US equities comparing **CNN Markets** and **Finviz** analyst forecasts, scoring each stock with a proprietary **ASR (Analyst Synthesis Rating)**, and outputting a score-weighted portfolio.

## Stack

- Python 3.10+ (stdlib + optional `tqdm`)
- **CNN** — 1Y price targets + analyst rating counts
- **Finviz** — consensus target price + recommendation (1=Strong Buy … 5=Sell)
- NASDAQ symbol directories (~5.4k common stocks)

## Usage

```bash
python3 run_screener.py
python3 run_lightweight.py          # rescore from cache
python3 run_screener.py --from-cache
```

```bash
python3 run_screener.py --min-analysts 15 --min-asr 70 --min-agreement 70
```

## ASR Rating (proprietary, 0–100)

| Component | Weight | Source |
|-----------|--------|--------|
| Upside | 30 pts | CNN + Finviz consensus, 6M scaled |
| Risk | 20 pts | CNN low-target floor, target spread |
| Coverage | 15 pts | CNN analyst count |
| Consensus | 20 pts | CNN vs Finviz agreement |
| Sentiment | 15 pts | CNN buy % + Finviz recommendation |

Grades: **A+** (90+) → **F** (<45). Labels: Strong Buy, Buy, Moderate Buy, Hold/Watch, Weak, Avoid.

## Filters (defaults)

| Param | Default |
|-------|---------|
| Min CNN analysts | 15 |
| Min ASR score | 65 |
| Min source agreement | 60% |
| Min 1Y median upside | 15% |
| Max 1Y median upside | 80% |
| Max low-target downside | 15% |

When both CNN and Finviz data exist, stocks must show **bullish consensus** and sufficient agreement.

## Pipeline

1. Load ticker universe
2. Fetch CNN forecast + ratings, Finviz target/recommendation (cached)
3. Build cross-source consensus
4. Compute ASR score, filter, rank
5. Allocate `$` budget across top picks

## Output

```
output/
  portfolio_report.html
  latest_scan.json
  forecast_cache.json
  sheets/01_scan_summary.csv
  sheets/02_portfolio_buys.csv
  sheets/03_top_picks_all.csv
```

## Layout

```
screener/
  cnn.py         CNN forecast + ratings
  finviz.py      Finviz analyst data
  consensus.py   cross-source comparison
  rating.py      ASR proprietary score
  scoring.py     filter + rank
  scanner.py     orchestration
  report.py      html/csv export
```

## Disclaimer

Research tool only — not financial advice.
