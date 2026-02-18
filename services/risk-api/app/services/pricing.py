"""LMSR pricing engine — Python port of the Go market engine's cost function.

Converts NWS ensemble exceedance probabilities into USD premiums via the
Logarithmic Market Scoring Rule.  For week-1 "naive" pricing, we initialise
a virtual LMSR market at the forecast probability and compute the fill price
for a single unit of coverage.  This gives a theoretically grounded premium
that incorporates both the probability estimate *and* the market-maker spread
implied by the liquidity parameter b.

Reference: Hanson, R. (2003) "Combinatorial Information Market Design"
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class PricingResult:
    risk_probability: float
    confidence_lower: float
    confidence_upper: float
    suggested_premium_usd: float
    pricing_model: str


def _log_sum_exp(xs: list[float]) -> float:
    """Numerically stable log-sum-exp (mirrors Go implementation)."""
    if not xs:
        return float("-inf")
    max_val = max(xs)
    if math.isinf(max_val) and max_val < 0:
        return float("-inf")
    return max_val + math.log(sum(math.exp(x - max_val) for x in xs))


def lmsr_cost(q_yes: float, q_no: float, b: float) -> float:
    """C(q) = b * ln(exp(q_yes/b) + exp(q_no/b))"""
    return b * _log_sum_exp([q_yes / b, q_no / b])


def lmsr_price(q_yes: float, q_no: float, b: float) -> float:
    """Instantaneous YES price (softmax)."""
    y = q_yes / b
    n = q_no / b
    max_val = max(y, n)
    exp_y = math.exp(y - max_val)
    exp_n = math.exp(n - max_val)
    return exp_y / (exp_y + exp_n)


def lmsr_trade_cost(q_yes: float, q_no: float, delta_yes: float, b: float) -> float:
    """Cost of buying delta_yes shares of YES."""
    return lmsr_cost(q_yes + delta_yes, q_no, b) - lmsr_cost(q_yes, q_no, b)


def _quantities_from_probability(p: float, b: float) -> tuple[float, float]:
    """Derive LMSR quantities that yield instantaneous price = p.

    With q_no = 0, solving p = exp(q_yes/b) / (exp(q_yes/b) + 1) gives
    q_yes = b * ln(p / (1 - p)).
    """
    p = max(0.001, min(0.999, p))
    q_yes = b * math.log(p / (1.0 - p))
    return q_yes, 0.0


def compute_premium(
    risk_probability: float,
    confidence_lower: float,
    confidence_upper: float,
    notional_usd: float | None = None,
    b: float | None = None,
) -> PricingResult:
    """Compute the LMSR-derived premium for a unit of weather risk coverage.

    1. Initialise a virtual market at the NWS forecast probability.
    2. Compute the fill price for 1 share of YES coverage.
    3. Scale by notional payout and add the loading factor.
    """
    if b is None:
        b = settings.default_liquidity_b
    if notional_usd is None:
        notional_usd = settings.notional_payout_usd

    q_yes, q_no = _quantities_from_probability(risk_probability, b)

    fill_cost = lmsr_trade_cost(q_yes, q_no, 1.0, b)
    raw_premium = fill_cost * notional_usd
    premium_usd = round(raw_premium * (1.0 + settings.loading_factor), 2)

    return PricingResult(
        risk_probability=round(risk_probability, 4),
        confidence_lower=round(confidence_lower, 4),
        confidence_upper=round(confidence_upper, 4),
        suggested_premium_usd=max(0.01, premium_usd),
        pricing_model=settings.pricing_model,
    )
