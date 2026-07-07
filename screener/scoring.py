"""Score stocks by CNN analyst upside vs downside for a 6-month horizon."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .cnn import CnnAnalystRatings, CnnForecast


@dataclass
class ScoredStock:
    symbol: str
    name: str
    exchange: str
    current_price: float
    median_target: float
    high_target: float
    low_target: float
    pct_median_1y: float
    pct_high_1y: float
    pct_low_1y: float
    gain_6m_median_pct: float
    gain_6m_high_pct: float
    downside_1y_pct: float
    upside_risk_ratio: float
    target_spread_pct: float
    composite_score: float
    num_analysts: int
    pct_analyst_buys: float
    last_updated: str | None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def scale_annual_to_months(annual_pct: float, months: float) -> float:
    """Scale a 12-month analyst return to a shorter holding period (sqrt-time)."""
    return annual_pct * math.sqrt(months / 12.0)


def score_forecast(
    forecast: CnnForecast,
    *,
    ratings: CnnAnalystRatings | None = None,
    name: str = "",
    exchange: str = "",
    horizon_months: float = 6.0,
    min_price: float = 5.0,
    min_median_upside_1y: float = 15.0,
    max_median_upside_1y: float = 80.0,
    max_downside_1y: float = 15.0,
    min_analysts: int = 15,
) -> ScoredStock | None:
    price = forecast.current_price
    if price < min_price:
        return None

    if ratings is None or ratings.num_analysts < min_analysts:
        return None

    median = forecast.pct_median
    high = forecast.pct_high
    low = forecast.pct_low

    if median < min_median_upside_1y or median > max_median_upside_1y:
        return None

    downside = max(0.0, -low)
    if downside > max_downside_1y:
        return None

    gain_6m_median = scale_annual_to_months(median, horizon_months)
    gain_6m_high = scale_annual_to_months(high, horizon_months)

    if gain_6m_median <= 0:
        return None

    # Skip likely bad/stale data: all targets identical at extreme upside
    if abs(median - low) < 1 and abs(median - high) < 1 and median > 100:
        return None

    spread = 0.0
    if forecast.median_target > 0:
        spread = ((forecast.high_target - forecast.low_target) / forecast.median_target) * 100.0

    upside_risk_ratio = gain_6m_median / (1.0 + downside)

    # Reward positive low target (analysts see no downside), penalize wide disagreement
    floor_bonus = 12.0 if low >= 0 else max(0.0, 12.0 - downside)
    spread_penalty = max(0.0, spread - 60.0) * 0.15

    # Higher upside, higher ceiling, lower downside, tighter analyst range → better score
    composite = (
        gain_6m_median * 0.40
        + gain_6m_high * 0.12
        + upside_risk_ratio * 6.0
        + floor_bonus * 0.35
        + max(0.0, 50.0 - spread) * 0.08
        - spread_penalty
    )

    return ScoredStock(
        symbol=forecast.symbol,
        name=name,
        exchange=exchange,
        current_price=round(price, 2),
        median_target=round(forecast.median_target, 2),
        high_target=round(forecast.high_target, 2),
        low_target=round(forecast.low_target, 2),
        pct_median_1y=round(median, 2),
        pct_high_1y=round(high, 2),
        pct_low_1y=round(low, 2),
        gain_6m_median_pct=round(gain_6m_median, 2),
        gain_6m_high_pct=round(gain_6m_high, 2),
        downside_1y_pct=round(downside, 2),
        upside_risk_ratio=round(upside_risk_ratio, 2),
        target_spread_pct=round(spread, 2),
        composite_score=round(composite, 2),
        num_analysts=ratings.num_analysts,
        pct_analyst_buys=round(ratings.pct_buys, 2),
        last_updated=forecast.last_updated,
    )


def rank_stocks(scored: list[ScoredStock], top_n: int = 30) -> list[ScoredStock]:
    return sorted(scored, key=lambda s: s.composite_score, reverse=True)[:top_n]
