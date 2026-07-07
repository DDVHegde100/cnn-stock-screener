"""Build a dollar allocation across top-ranked picks."""

from __future__ import annotations

from dataclasses import dataclass

from .scoring import ScoredStock


@dataclass
class PortfolioLine:
    rank: int
    symbol: str
    name: str
    current_price: float
    weight_pct: float
    allocation_usd: float
    shares: int
    actual_invested_usd: float
    expected_6m_gain_pct: float
    expected_6m_profit_usd: float
    composite_score: float

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def build_portfolio(
    picks: list[ScoredStock],
    budget: float = 10_000.0,
    *,
    max_weight: float = 0.10,
    min_weight: float = 0.01,
    min_positions: int = 30,
) -> tuple[list[PortfolioLine], dict]:
    if not picks:
        return [], {"budget": budget, "invested": 0.0, "cash_remaining": budget}

    # Use enough candidates so we can fill min_positions after skipping unaffordable names
    candidates = picks[: max(min_positions * 2, len(picks))]
    scores = [max(p.composite_score, 0.01) for p in candidates]
    total_score = sum(scores)
    raw_weights = [s / total_score for s in scores]

    capped = [min(w, max_weight) for w in raw_weights]
    cap_total = sum(capped)
    weights = [w / cap_total for w in capped]

    active = [(p, w) for p, w in zip(candidates, weights) if w >= min_weight]
    if not active:
        active = [(candidates[0], 1.0)]

    active_total = sum(w for _, w in active)
    active = [(p, w / active_total) for p, w in active]

    lines: list[PortfolioLine] = []
    invested = 0.0
    rank = 0

    for pick, weight in active:
        allocation = round(budget * weight, 2)
        shares = int(allocation // pick.current_price) if pick.current_price > 0 else 0
        if shares <= 0:
            continue

        rank += 1
        actual = round(shares * pick.current_price, 2)
        expected_profit = round(actual * (pick.gain_6m_median_pct / 100.0), 2)

        lines.append(
            PortfolioLine(
                rank=rank,
                symbol=pick.symbol,
                name=pick.name,
                current_price=pick.current_price,
                weight_pct=round(weight * 100, 2),
                allocation_usd=allocation,
                shares=shares,
                actual_invested_usd=actual,
                expected_6m_gain_pct=pick.gain_6m_median_pct,
                expected_6m_profit_usd=expected_profit,
                composite_score=pick.composite_score,
            )
        )
        invested += actual
        if len(lines) >= min_positions:
            break

    # Recompute weights based on actual invested amounts
    if invested > 0:
        for line in lines:
            line.weight_pct = round((line.actual_invested_usd / invested) * 100, 2)

    summary = {
        "budget": budget,
        "invested": round(invested, 2),
        "cash_remaining": round(budget - invested, 2),
        "positions": len(lines),
        "expected_6m_profit_usd": round(sum(l.expected_6m_profit_usd for l in lines), 2),
        "expected_6m_return_pct": round(
            (sum(l.expected_6m_profit_usd for l in lines) / invested * 100) if invested else 0.0,
            2,
        ),
    }
    return lines, summary
