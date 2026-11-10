"""Read-only descriptive top-of-book research; no calibrated price forecast.

OFI convention: Cont, Kukanov & Stoikov, arXiv:1011.6402.
No feed, execution, latency, or directional recommendation is provided.
"""


import math
import re
from datetime import datetime, timezone
from fractions import Fraction


def _number(value: object, name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    # Keep exact tick/quantity integers for comparisons and signed differences.
    return value


def _sum(values) -> int | float:
    """Preserve integer terms before rounding a mixed numeric flow to float."""
    values = tuple(values)
    if all(isinstance(value, int) for value in values):
        return sum(values)
    if not any(isinstance(value, int) for value in values):
        try:
            return math.fsum(values)
        except OverflowError:
            pass  # Large cancelling terms may overflow fsum's intermediate partials.
    return float(sum(Fraction(value) for value in values))


def book_features(
    bid: float, ask: float, bid_size: float, ask_size: float
) -> dict:
    """Describe a single synchronous top-of-book snapshot in common units."""
    bid, ask, bid_size, ask_size = (
        _number(value, name)
        for name, value in zip(
            ("bid", "ask", "bid_size", "ask_size"),
            (bid, ask, bid_size, ask_size),
        )
    )
    if bid <= 0 or ask <= 0 or bid > ask:
        raise ValueError("prices must be positive and book must not be crossed")
    if bid_size < 0 or ask_size < 0 or (bid_size == 0 and ask_size == 0):
        raise ValueError("queue sizes must be nonnegative with positive total")
    size_scale = max(bid_size, ask_size)
    qb, qa = bid_size / size_scale, ask_size / size_scale
    total_size = qb + qa
    imbalance = _sum((bid_size, -ask_size)) / size_scale / total_size
    spread = _sum((ask, -bid))
    mid = bid + spread / 2
    return {
        "quoted_spread": spread,
        "mid": mid,
        "spread_bps": spread / mid * 10_000,
        "queue_imbalance": imbalance,
        "weighted_midpoint": bid + spread * (qb / total_size),
        "model_status": "unvalidated",
        "data_requirements": [
            "Synchronous best bid/ask and displayed queue sizes from one venue.",
            "Prices in a common currency and sizes in a common quantity unit.",
            "Weighted midpoint is not a calibrated microprice or fill estimate.",
        ],
    }


def order_flow_imbalance(events: list[dict]) -> dict:
    """Sum Cont signed top-of-book changes; the first event is a baseline."""
    if not isinstance(events, list) or len(events) < 2:
        raise ValueError("at least two quote events are required")
    if len(events) > 10_000:
        raise ValueError("maximum 10000 quote events per calculation")
    previous_time = None
    previous_kind = None
    clean = []
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("each event must be a quote dictionary")
        try:
            quote = {name: _number(event[name], name) for name in (
                "bid", "ask", "bid_size", "ask_size"
            )}
            book_features(**quote)
            timestamp = event["timestamp"]
        except KeyError as exc:
            raise ValueError(f"missing event field: {exc.args[0]}") from exc
        if isinstance(timestamp, str):
            # datetime truncates finer fractions; require lossless ordering instead.
            if any(any(digit != "0" for digit in fraction[6:])
                   for fraction in re.findall(r"[.,](\d+)", timestamp)):
                raise ValueError("ISO precision is limited to microseconds; use integer timestamps for finer clocks")
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError("timezone is required")
                current_time = parsed.astimezone(timezone.utc)
            except (ValueError, OverflowError) as exc:
                raise ValueError("timestamp must be timezone-aware ISO 8601") from exc
            kind = "iso"
        else:
            _number(timestamp, "timestamp")
            if timestamp < 0:
                raise ValueError("numeric timestamps must be nonnegative")
            current_time = timestamp  # Preserve integer exchange/nanosecond precision.
            kind = "numeric"
        if previous_time is not None and (
            kind != previous_kind or current_time <= previous_time
        ):
            raise ValueError("timestamps must be strictly increasing in a consistent format")
        previous_time, previous_kind = current_time, kind
        clean.append({"timestamp": timestamp, **quote})
    contributions = []
    for old, new in zip(clean, clean[1:]):
        try:
            ofi = _sum((
                (new["bid"] >= old["bid"]) * new["bid_size"],
                -(new["bid"] <= old["bid"]) * old["bid_size"],
                -(new["ask"] <= old["ask"]) * new["ask_size"],
                (new["ask"] >= old["ask"]) * old["ask_size"],
            ))
        except OverflowError as exc:
            raise ValueError("OFI exceeds finite numeric range") from exc
        contributions.append({"timestamp": new["timestamp"], "ofi": ofi})
    try:
        total_ofi = _sum(item["ofi"] for item in contributions)
    except OverflowError as exc:
        raise ValueError("OFI total exceeds finite numeric range") from exc
    return {
        "total_ofi": total_ofi,
        "transition_count": len(contributions),
        "contributions": contributions,
        "model_status": "unvalidated",
        "data_requirements": [
            "Ordered event-level best quotes and sizes, common venue/units.",
            "Complete updates and increasing exchange timestamps or sequence-normalized times.",
            "ISO timestamps retain microsecond precision; use integer timestamps for finer clocks.",
            "Sampled snapshots omit intervening flow; gaps compromise OFI.",
            "Descriptive displayed flow only, not a directional recommendation or latency advantage.",
        ],
    }
