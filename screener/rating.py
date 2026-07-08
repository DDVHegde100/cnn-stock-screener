"""Proprietary Analyst Synthesis Rating (ASR)."""

from __future__ import annotations

from dataclasses import dataclass

from .cnn import CnnAnalystRatings, CnnForecast
from .consensus import SourceComparison
from .finviz import FinvizForecast
from .utils import scale_annual_to_months


@dataclass
class AsrRating:
    score: float
    grade: str
    upside_pts: float
    risk_pts: float
    coverage_pts: float
    consensus_pts: float
    sentiment_pts: float
    label: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _letter_grade(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 80:
        return "A-"
    if score >= 75:
        return "B+"
    if score >= 70:
        return "B"
    if score >= 65:
        return "B-"
    if score >= 60:
        return "C+"
    if score >= 55:
        return "C"
    if score >= 50:
        return "C-"
    if score >= 45:
        return "D"
    return "F"


def _label(score: float) -> str:
    if score >= 85:
        return "Strong Buy"
    if score >= 75:
        return "Buy"
    if score >= 65:
        return "Moderate Buy"
    if score >= 55:
        return "Hold / Watch"
    if score >= 45:
        return "Weak"
    return "Avoid"


def compute_asr(
    forecast: CnnForecast,
    ratings: CnnAnalystRatings,
    consensus: SourceComparison,
    finviz: FinvizForecast | None,
    *,
    horizon_months: float = 6.0,
) -> AsrRating:
    gain_6m = scale_annual_to_months(consensus.consensus_upside_pct, horizon_months)

    # Upside (0–30): 6M consensus gain mapped to points
    upside_pts = min(30.0, max(0.0, gain_6m * 0.45))

    # Risk (0–20): CNN low-target floor + analyst target spread
    downside = max(0.0, -forecast.pct_low)
    spread = 0.0
    if forecast.median_target > 0:
        spread = ((forecast.high_target - forecast.low_target) / forecast.median_target) * 100.0
    risk_pts = max(0.0, 20.0 - downside * 0.5 - max(0.0, spread - 50.0) * 0.08)

    # Coverage (0–15): CNN analyst count
    coverage_pts = min(15.0, ratings.num_analysts / 40.0 * 15.0)

    # Consensus (0–20): cross-source agreement
    consensus_pts = consensus.source_agreement_pct / 100.0 * 20.0
    if consensus.sources_available >= 2 and not consensus.bullish_consensus:
        consensus_pts *= 0.5

    # Sentiment (0–15): CNN buy % + Finviz recommendation
    cnn_sent = ratings.pct_buys / 100.0 * 10.0
    fv_sent = (finviz.sentiment_score or 50.0) / 100.0 * 5.0 if finviz else 2.5
    sentiment_pts = min(15.0, cnn_sent + fv_sent)

    score = round(upside_pts + risk_pts + coverage_pts + consensus_pts + sentiment_pts, 1)

    return AsrRating(
        score=score,
        grade=_letter_grade(score),
        upside_pts=round(upside_pts, 1),
        risk_pts=round(risk_pts, 1),
        coverage_pts=round(coverage_pts, 1),
        consensus_pts=round(consensus_pts, 1),
        sentiment_pts=round(sentiment_pts, 1),
        label=_label(score),
    )
