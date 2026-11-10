"""Shared cash-price indicators, extracted unchanged from equity research.

Callers must supply validated, nonempty, positive cash-underlier OHLCV bars
and a consistent raw/split/total-return adjustment basis. These helpers do not
validate instrument identity, source clocks, sessions or price domains. They
must not be used on option-premium or futures-contract price series. Derivatives
research must supply the validated positive cash-index underlier bars instead.
Warnings are appended to the caller's list; bars are never mutated. Windows,
seeding, formulas and missing-history behavior remain equity-compatible.
"""

import math
import statistics


def ema(values, period):
    if len(values) < period:
        return None
    average = statistics.mean(values[:period])
    alpha = 2 / (period + 1)
    for value in values[period:]:
        average += alpha * (value - average)
    return average


def wilder(values, period=14):
    if len(values) < period:
        return None
    average = statistics.mean(values[:period])
    for value in values[period:]:
        average = (average * (period - 1) + value) / period
    return average


def technical(bars, adjustment, warnings):
    closes = [bar.get("adjusted_close", bar["close"]) for bar in bars]
    metrics = {f"sma{n}": statistics.mean(closes[-n:]) if len(closes) >= n else None
               for n in (20, 50, 200)}
    metrics.update({f"ema{n}": ema(closes, n) for n in (12, 26)})
    metrics["macd"] = (metrics["ema12"] - metrics["ema26"]
                       if len(closes) >= 26 else None)
    differences = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = wilder([max(value, 0) for value in differences])
    losses = wilder([max(-value, 0) for value in differences])
    metrics["rsi14"] = (None if gains is None else
                        (50 if gains == 0 and losses == 0 else
                         100 if losses == 0 else 100 - 100 / (1 + gains / losses)))
    scales = [closes[i] / bar["close"] for i, bar in enumerate(bars)]
    ranges = [max((bars[i]["high"] - bars[i]["low"]) * scales[i],
                  abs(bars[i]["high"] * scales[i] - closes[i - 1]),
                  abs(bars[i]["low"] * scales[i] - closes[i - 1]))
              for i in range(1, len(bars))]
    metrics["atr14"] = wilder(ranges)
    if adjustment == "total_return" and any(scale != 1 for scale in scales):
        metrics["atr14"] = None
        warnings.append("ATR unavailable: total-return adjusted close differs from OHLC basis")
    returns = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    metrics["vol20"] = (statistics.stdev(returns[-20:]) * math.sqrt(252)
                        if len(returns) >= 20 else None)
    peak, drawdown = closes[0], 0.0
    for close in closes:
        peak = max(peak, close)
        drawdown = min(drawdown, close / peak - 1)
    metrics["max_drawdown"] = drawdown
    for period in (21, 63, 252):
        metrics[f"return{period}"] = (closes[-1] / closes[-period - 1] - 1
                                        if len(closes) > period else None)
    metrics["momentum12_1"] = closes[-22] / closes[-253] - 1 if len(closes) >= 253 else None
    metrics["dollar_volume20"] = (statistics.mean(
        bar["close"] * bar["volume"] for bar in bars[-20:]) if len(bars) >= 20 else None)
    return metrics
