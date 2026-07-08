"""Score stocks using multi-source analyst consensus and ASR rating."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .cnn import CnnAnalystRatings, CnnForecast
from .consensus import build_consensus
from .finviz import FinvizForecast
from .rating import compute_asr
from .utils import scale_annual_to_months


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
    finviz_target: float | None
    finviz_upside_pct: float | None
    finviz_recom: float | None
    consensus_upside_pct: float
    source_agreement_pct: float
    sources_available: int
    asr_score: float
    asr_grade: str
    asr_label: str
    last_updated: str | None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def score_forecast(
    forecast: CnnForecast,
    *,
    ratings: CnnAnalystRatings | None = None,
    finviz: FinvizForecast | None = None,
    name: str = "",
    exchange: str = "",
    horizon_months: float = 6.0,
    min_price: float = 5.0,
    min_median_upside_1y: float = 15.0,
    max_median_upside_1y: float = 80.0,
    max_downside_1y: float = 15.0,
    min_analysts: int = 15,
    min_asr: float = 65.0,
    min_source_agreement: float = 60.0,
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

    consensus_cmp = build_consensus(forecast, ratings, finviz)
    effective_upside = consensus_cmp.consensus_upside_pct

    gain_6m_median = scale_annual_to_months(effective_upside, horizon_months)
    gain_6m_high = scale_annual_to_months(high, horizon_months)

    if gain_6m_median <= 0:
        return None

    if abs(median - low) < 1 and abs(median - high) < 1 and median > 100:
        return None

    if consensus_cmp.sources_available >= 2:
        if consensus_cmp.source_agreement_pct < min_source_agreement:
            return None
        if not consensus_cmp.bullish_consensus:
            return None

    spread = 0.0
    if forecast.median_target > 0:
        spread = ((forecast.high_target - forecast.low_target) / forecast.median_target) * 100.0

    upside_risk_ratio = gain_6m_median / (1.0 + downside)

    asr = compute_asr(forecast, ratings, consensus_cmp, finviz, horizon_months=horizon_months)
    if asr.score < min_asr:
        return None

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
        composite_score=asr.score,
        num_analysts=ratings.num_analysts,
        pct_analyst_buys=round(ratings.pct_buys, 2),
        finviz_target=round(finviz.target_price, 2) if finviz and finviz.target_price else None,
        finviz_upside_pct=finviz.upside_pct if finviz else None,
        finviz_recom=finviz.recommendation if finviz else None,
        consensus_upside_pct=consensus_cmp.consensus_upside_pct,
        source_agreement_pct=consensus_cmp.source_agreement_pct,
        sources_available=consensus_cmp.sources_available,
        asr_score=asr.score,
        asr_grade=asr.grade,
        asr_label=asr.label,
        last_updated=forecast.last_updated,
    )


def rank_stocks(scored: list[ScoredStock], top_n: int = 30) -> list[ScoredStock]:
    return sorted(scored, key=lambda s: s.asr_score, reverse=True)[:top_n]
