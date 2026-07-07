"""Generate HTML and JSON reports from scan results."""

from __future__ import annotations

import json
from pathlib import Path

from .scanner import ScanResult


def write_json_report(result: ScanResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2))


def write_html_report(result: ScanResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = ""
    for line in result.portfolio:
        rows += f"""
        <tr>
          <td>{line.rank}</td>
          <td><strong>{line.symbol}</strong></td>
          <td>{line.name[:40]}</td>
          <td>${line.current_price:,.2f}</td>
          <td>{line.weight_pct:.1f}%</td>
          <td>${line.allocation_usd:,.2f}</td>
          <td>{line.shares}</td>
          <td>${line.actual_invested_usd:,.2f}</td>
          <td class="green">+{line.expected_6m_gain_pct:.1f}%</td>
          <td class="green">${line.expected_6m_profit_usd:,.2f}</td>
          <td>{line.composite_score:.1f}</td>
        </tr>"""

    pick_rows = ""
    for i, p in enumerate(result.top_picks, 1):
        pick_rows += f"""
        <tr>
          <td>{i}</td>
          <td><strong>{p.symbol}</strong></td>
          <td>${p.current_price:,.2f}</td>
          <td>${p.median_target:,.2f}</td>
          <td>${p.high_target:,.2f}</td>
          <td>${p.low_target:,.2f}</td>
          <td class="green">+{p.pct_median_1y:.1f}%</td>
          <td class="green">+{p.pct_high_1y:.1f}%</td>
          <td class="{'red' if p.pct_low_1y < 0 else 'green'}">{p.pct_low_1y:+.1f}%</td>
          <td class="green">+{p.gain_6m_median_pct:.1f}%</td>
          <td>{p.upside_risk_ratio:.2f}</td>
          <td>{p.composite_score:.1f}</td>
        </tr>"""

    summary = result.portfolio_summary
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>CNN Stock Screener — Portfolio</title>
  <style>
    :root {{
      --bg: #0f1419; --card: #1a2332; --text: #e7ecf3; --muted: #8b9cb3;
      --green: #3dd68c; --red: #ff6b6b; --accent: #4dabf7; --border: #2a3544;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 24px; }}
    h1 {{ font-size: 1.6rem; margin-bottom: 8px; }}
    .sub {{ color: var(--muted); margin-bottom: 24px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 28px; }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }}
    .card .val {{ font-size: 1.5rem; font-weight: 700; color: var(--accent); }}
    .card .lbl {{ color: var(--muted); font-size: 0.85rem; margin-top: 4px; }}
    h2 {{ margin: 28px 0 12px; font-size: 1.1rem; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 10px; overflow: hidden; font-size: 0.88rem; }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ background: #121a24; color: var(--muted); font-weight: 600; }}
    tr:hover td {{ background: rgba(77,171,247,0.05); }}
    .green {{ color: var(--green); }}
    .red {{ color: var(--red); }}
    .disclaimer {{ margin-top: 32px; padding: 16px; background: #1e1610; border: 1px solid #4a3520; border-radius: 8px; color: #c4a574; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <h1>CNN Analyst Stock Screener</h1>
  <p class="sub">Scanned {result.universe_size:,} tickers · {result.qualified_count} qualified · {result.duration_sec}s · {result.scanned_at[:19]} UTC</p>

  <div class="cards">
    <div class="card"><div class="val">${summary['budget']:,.0f}</div><div class="lbl">Budget</div></div>
    <div class="card"><div class="val">${summary['invested']:,.0f}</div><div class="lbl">Invested</div></div>
    <div class="card"><div class="val">${summary['cash_remaining']:,.0f}</div><div class="lbl">Cash Left</div></div>
    <div class="card"><div class="val green">+{summary['expected_6m_return_pct']:.1f}%</div><div class="lbl">Expected 6M Return</div></div>
    <div class="card"><div class="val green">${summary['expected_6m_profit_usd']:,.0f}</div><div class="lbl">Expected 6M Profit</div></div>
    <div class="card"><div class="val">{summary['positions']}</div><div class="lbl">Positions</div></div>
  </div>

  <h2>$10,000 Portfolio Allocation (Top {len(result.portfolio)})</h2>
  <table>
    <thead>
      <tr>
        <th>#</th><th>Ticker</th><th>Company</th><th>Price</th><th>Weight</th>
        <th>Target $</th><th>Shares</th><th>Invested</th><th>6M Gain</th><th>6M Profit</th><th>Score</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <h2>Top {len(result.top_picks)} Picks — CNN Analyst Forecasts</h2>
  <table>
    <thead>
      <tr>
        <th>#</th><th>Ticker</th><th>Price</th><th>Median Target</th><th>High Target</th><th>Low Target</th>
        <th>1Y Median</th><th>1Y High</th><th>1Y Low</th><th>6M Est.</th><th>Upside/Risk</th><th>Score</th>
      </tr>
    </thead>
    <tbody>{pick_rows}</tbody>
  </table>

  <div class="disclaimer">
    <strong>Disclaimer:</strong> This tool is for informational and educational purposes only — not financial advice.
    CNN analyst targets are 12-month estimates; 6-month figures use √time scaling. Past analyst accuracy does not guarantee future results.
    Always do your own research before investing.
  </div>
</body>
</html>"""

    path.write_text(html)
