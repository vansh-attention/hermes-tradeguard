"""Pure, unvalidated derivatives research heuristics; never probabilities.

Direction uses cash-index technical observations, not option-premium or futures
candles. Contract quality is only a spread penalty. These engineering thresholds
are not performance validation, expected return or execution assurances.
"""

import math
from collections.abc import Mapping

POLICY_VERSION = "derivatives_policy_v1"

_PAIRS = (("last_close", "sma20"), ("sma20", "sma50"),
          ("sma50", "sma200"), ("last_close", "sma200"))


def _finite_number(value):
    """Native int/float only; avoid leaking OverflowError for excessive ints."""
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def directional_support(metrics, side):
    """Return cash-underlier support on a fixed four-comparison denominator.

    ``metrics`` is a mapping of last_close, sma20, sma50 and sma200 to finite
    native int/float observations. Missing/None required evidence returns None,
    never a rescaled partial score. ``side`` must be exactly long or short.
    Other fields (including unsigned OI/volume) do not influence direction.
    Upstream cash-price validation, not this comparison policy, owns positivity.
    """
    if not isinstance(side, str) or side not in ("long", "short"):
        raise ValueError("side must be long or short")
    if not isinstance(metrics, Mapping):
        raise ValueError("metrics must be a mapping")
    if any(metrics.get(key) is None for pair in _PAIRS for key in pair):
        return None
    points = []
    for left, right in _PAIRS:
        a, b = metrics[left], metrics[right]
        if not _finite_number(a) or not _finite_number(b):
            raise ValueError("invalid directional input; finite int/float required")
        comparison = (a > b) - (a < b)
        points.append(.5 if comparison == 0 else
                      float(comparison == (1 if side == "long" else -1)))
    return sum(points) / len(_PAIRS)


def research_interest(direction, spread_fraction, *, blockers):
    """Return gated, uncalibrated interest; never a strong-buy/profit probability.

    ``blockers`` is a required built-in list of nonempty strings, validated
    before any early return. A blocker or None input yields null score AND
    quality. Only complete ungated inputs are scored: finite native direction
    in [0, 1], nonnegative finite native spread fraction, no bool/coercion.
    The score is round(direction * max(0, 1 - spread_fraction / .02), 4);
    verdict uses the rounded score with an inclusive .6 candidate threshold.
    A spread above 2% has zero quality here; entry-eligibility spread blockers
    belong to the caller. Never shrink the denominator for missing evidence.
    """
    if (type(blockers) is not list
            or any(not isinstance(blocker, str) or not blocker.strip() for blocker in blockers)):
        raise ValueError("blockers must be a list of nonempty strings")
    if blockers or direction is None or spread_fraction is None:
        return {"score": None, "contract_quality": None, "verdict": "ABSTAIN",
                "strong_buy": False}
    if not _finite_number(direction) or not 0 <= direction <= 1:
        raise ValueError("invalid directional support; expected finite int/float in [0, 1]")
    if not _finite_number(spread_fraction) or spread_fraction < 0:
        raise ValueError("invalid spread fraction; expected nonnegative finite int/float")
    # Engineering weights, not calibrated expected return or empirical optima.
    quality = max(0.0, 1 - spread_fraction / .02)
    score = round(direction * quality, 4)
    return {"score": score, "contract_quality": quality,
            "verdict": "RESEARCH_CANDIDATE" if score >= .6 else "LOW_INTEREST",
            "strong_buy": False}
