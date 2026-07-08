"""Compare analyst forecasts across data sources."""

from __future__ import annotations

from dataclasses import dataclass

from .cnn import CnnAnalystRatings, CnnForecast
from .finviz import FinvizForecast


@dataclass
class SourceComparison:
    symbol: str
    cnn_upside_pct: float
    finviz_upside_pct: float | None
    consensus_upside_pct: float
    target_spread_pct: float | None
    source_agreement_pct: float
    sources_available: int
    bullish_consensus: bool

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _agreement_pct(a: float, b: float) -> float:
    """100 = perfect agreement on upside magnitude/direction."""
    if a == 0 and b == 0:
        return 100.0
    denom = max(abs(a), abs(b), 1.0)
    diff = abs(a - b) / denom * 100.0
    direction_penalty = 30.0 if (a >= 0) != (b >= 0) else 0.0
    return max(0.0, 100.0 - diff - direction_penalty)


def build_consensus(
    forecast: CnnForecast,
    ratings: CnnAnalystRatings,
    finviz: FinvizForecast | None,
    *,
    cnn_weight: float = 0.6,
    finviz_weight: float = 0.4,
) -> SourceComparison:
    cnn_up = forecast.pct_median
    fv_up = finviz.upside_pct if finviz else None

    sources = 1
    if fv_up is not None:
        sources = 2
        consensus = cnn_up * cnn_weight + fv_up * finviz_weight
        agreement = _agreement_pct(cnn_up, fv_up)
        spread = abs(forecast.median_target - (finviz.target_price or forecast.median_target))
        spread_pct = (spread / forecast.median_target * 100.0) if forecast.median_target else None
    else:
        consensus = cnn_up
        agreement = 100.0
        spread_pct = None

    finviz_bullish = finviz is None or (
        (finviz.upside_pct or 0) > 0 and (finviz.recommendation or 3) <= 2.5
    )
    cnn_bullish = cnn_up > 0 and ratings.pct_buys >= 50
    bullish = cnn_bullish and finviz_bullish

    return SourceComparison(
        symbol=forecast.symbol,
        cnn_upside_pct=round(cnn_up, 2),
        finviz_upside_pct=round(fv_up, 2) if fv_up is not None else None,
        consensus_upside_pct=round(consensus, 2),
        target_spread_pct=round(spread_pct, 2) if spread_pct is not None else None,
        source_agreement_pct=round(agreement, 2),
        sources_available=sources,
        bullish_consensus=bullish,
    )
