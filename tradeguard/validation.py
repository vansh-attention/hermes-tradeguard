"""Read-only, chronological next-open research; not a validated trading model."""

import math
from datetime import date
from functools import wraps
from statistics import fmean, median, pstdev, stdev

FEATURE_NAMES = ("return5", "return21", "return63", "vol20", "close_ma200_gap")
WARMUP_INDEX = 199


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _validate_bars(bars: list[dict], adjustment: str) -> list[dict]:
    if adjustment not in ("raw", "split"):
        raise ValueError("adjustment must explicitly be 'raw' or 'split'; total_return is unsupported")
    if not isinstance(bars, list):
        raise ValueError("bars must be a list of daily OHLCV dictionaries")
    if len(bars) > 4000:
        raise ValueError("bars exceed the fixed maximum of 4000 rows")
    clean = []
    previous = None
    for index, bar in enumerate(bars):
        if not isinstance(bar, dict):
            raise ValueError(f"bar {index} must be a dictionary")
        try:
            label = bar["date"]
            if not isinstance(label, str) or len(label) != 10:
                raise ValueError("daily date must be YYYY-MM-DD")
            parsed = date.fromisoformat(label)
            if parsed.isoformat() != label:
                raise ValueError("daily date must be YYYY-MM-DD")
            if previous is not None and parsed <= previous:
                raise ValueError("bar dates must be unique and strictly chronological")
            previous = parsed
            values = {name: _number(bar[name], f"bar {index} {name}") for name in (
                "open", "high", "low", "close", "volume"
            )}
        except KeyError as exc:
            raise ValueError(f"bar {index} missing required field {exc.args[0]}") from exc
        if any(values[name] <= 0 for name in ("open", "high", "low", "close")):
            raise ValueError("OHLC prices must be positive")
        if not values["low"] <= min(values["open"], values["close"]) <= max(
            values["open"], values["close"]
        ) <= values["high"]:
            raise ValueError("OHLC prices are inconsistent")
        if values["volume"] < 0:
            raise ValueError("volume must be nonnegative")
        if "adjusted_close" in bar and _number(bar["adjusted_close"], "adjusted_close") <= 0:
            raise ValueError("adjusted_close must be positive when supplied")
        if "adjustment" in bar and bar["adjustment"] != adjustment:
            raise ValueError("row adjustment contradicts the series adjustment")
        clean.append({"date": label, **values})
    _check_daily_spacing(clean)
    return clean


def _check_daily_spacing(bars: list[dict]) -> None:
    """Reject obvious undersampling; this is not an exchange-session calendar."""
    gaps = [(date.fromisoformat(bars[i]["date"]) - date.fromisoformat(bars[i - 1]["date"])).days
            for i in range(1, len(bars))]
    # Short OOS slices may consist solely of a legitimate weekend/holiday gap.
    sparse = len(gaps) >= 10 and (median(gaps) > 1 or fmean(gaps) > 2)
    if gaps and (max(gaps) > 7 or sparse):
        raise ValueError("sparse daily history/session gaps; cannot assume 252 daily observations per year")


def _simple_return(end: float, start: float) -> float:
    value = _number(end / start - 1, "derived return")
    if value <= -1:
        raise ValueError("derived return exceeds finite numeric precision")
    return value


def _features(closes: list[float], t: int) -> list[float]:
    returns = [_simple_return(closes[j], closes[j - 1]) for j in range(t - 19, t + 1)]
    return [_simple_return(closes[t], closes[t - lag]) for lag in (5, 21, 63)] + [
        stdev(returns), _simple_return(closes[t], fmean(closes[t - 199:t + 1])),
    ]


def _solve(matrix: list[list[float]], target: list[float]) -> list[float]:
    """Solve a small dense system with partial-pivot Gaussian elimination."""
    size = len(target)
    rows = [list(row) + [value] for row, value in zip(matrix, target)]
    for k in range(size):
        pivot = max(range(k, size), key=lambda j: abs(rows[j][k]))
        rows[k], rows[pivot] = rows[pivot], rows[k]
        if rows[k][k] == 0:
            raise ValueError("ridge system is singular")
        for j in range(k + 1, size):
            factor = rows[j][k] / rows[k][k]
            for col in range(k, size + 1):
                rows[j][col] -= factor * rows[k][col]
    result = [0.0] * size
    for k in range(size - 1, -1, -1):
        result[k] = (rows[k][-1] - math.fsum(
            rows[k][j] * result[j] for j in range(k + 1, size)
        )) / rows[k][k]
    return result


def _fit(x: list[list[float]], y: list[float], alpha: float) -> dict:
    """Minimize sum squared residuals + alpha*||beta||²; intercept unpenalized."""
    width = len(FEATURE_NAMES)
    means = [fmean(row[k] for row in x) for k in range(width)]
    scales = [pstdev(row[k] for row in x) or 1.0 for k in range(width)]
    z = [[(value - means[k]) / scales[k] for k, value in enumerate(row)] for row in x]
    mean_y = fmean(y)
    matrix = [[math.fsum(row[k] * row[l] for row in z) + (alpha if k == l else 0)
               for l in range(width)] for k in range(width)]
    target = [math.fsum(row[k] * (value - mean_y) for row, value in zip(z, y))
              for k in range(width)]
    return {
        "feature_means": dict(zip(FEATURE_NAMES, means)),
        "feature_scales": dict(zip(FEATURE_NAMES, scales)),
        "coefficients": dict(zip(FEATURE_NAMES, _solve(matrix, target))),
        "training_mean": mean_y,
    }


def _predict(fit: dict, row: list[float]) -> float:
    return fit["training_mean"] + math.fsum(
        (value - fit["feature_means"][name]) / fit["feature_scales"][name]
        * fit["coefficients"][name] for name, value in zip(FEATURE_NAMES, row)
    )


def _portfolio(predictions: list[dict], positions: list[int], fee: float) -> tuple[dict, list[dict]]:
    """Self-financing long/cash wealth, fees charged on traded wealth each side."""
    wealth = gross_wealth = peak = 1.0
    max_drawdown = total_cost = 0.0
    previous = turnover = trade_count = entries = 0
    observations = []
    for i, (prediction, position) in enumerate(zip(predictions, positions)):
        before = wealth
        change = abs(position - previous)
        rebalance_cost = wealth * fee * change
        wealth -= rebalance_cost
        gross_return = position * prediction["actual_return"]
        wealth *= 1 + gross_return
        gross_wealth *= 1 + gross_return
        liquidation = int(i == len(predictions) - 1) * position
        liquidation_cost = wealth * fee * liquidation
        wealth -= liquidation_cost
        total_cost += rebalance_cost + liquidation_cost
        turnover += change + liquidation
        trade_count += change + liquidation
        entries += int(position > previous)
        peak = max(peak, wealth)
        max_drawdown = max(max_drawdown, 1 - wealth / peak)
        observations.append({
            "position": position,
            "gross_return": gross_return,
            "net_return": wealth / before - 1,
            "rebalance_cost": rebalance_cost,
            "entry_cost": rebalance_cost if position > previous else 0.0,
            "liquidation_cost": liquidation_cost,
            "turnover": change + liquidation,
            "ending_wealth": wealth,
        })
        previous = position
    returns = [row["net_return"] for row in observations]
    volatility = stdev(returns) if len(returns) > 1 else 0.0
    return {
        "start_date": predictions[0]["entry_date"],
        "end_date": predictions[-1]["exit_date"],
        "ending_wealth": wealth,
        "gross_ending_wealth": gross_wealth,
        "total_return": wealth - 1,
        "gross_total_return": gross_wealth - 1,
        "sharpe": fmean(returns) / volatility * math.sqrt(252) if volatility else None,
        "annualization": 252,
        "riskfree": 0.0,
        "max_drawdown": max_drawdown,
        "turnover": turnover,
        "trade_count": trade_count,
        "completed_round_trips": entries,
        "total_cost": total_cost,
        "total_cost_rate": fee * turnover,
    }, observations


def _check_finite_output(value: object) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("research result exceeds finite numeric range")
    if isinstance(value, dict):
        for item in value.values():
            _check_finite_output(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_finite_output(item)


def _finite_research(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            report = function(*args, **kwargs)
            _check_finite_output(report)
            return report
        except ArithmeticError as exc:
            raise ValueError("research inputs exceed finite numeric range") from exc
    return checked


@_finite_research
def walk_forward(
    bars: list[dict],
    min_train: int = 252,
    retrain_every: int = 21,
    cost_bps: float = 5.0,
    ridge_alpha: float = 10.0,
    *,
    adjustment: str,
) -> dict:
    """Evaluate expanding training windows with labels ending strictly before t."""
    for name, value in (("min_train", min_train), ("retrain_every", retrain_every)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    cost_bps = _number(cost_bps, "cost_bps")
    ridge_alpha = _number(ridge_alpha, "ridge_alpha")
    if not 0 <= cost_bps < 10_000:
        raise ValueError("cost_bps must be in [0, 10000)")
    if ridge_alpha <= 0:
        raise ValueError("ridge_alpha must be strictly positive")
    bars = _validate_bars(bars, adjustment)
    if len(bars) < min_train + 204:
        raise ValueError("no out-of-sample samples: need at least min_train + 204 daily bars")
    # A dense training prefix must not hide sparse intervals in the measured portfolio.
    _check_daily_spacing(bars[202 + min_train:])
    predictions, fits = [], []
    closes = [bar["close"] for bar in bars]
    features = {t: _features(closes, t) for t in range(WARMUP_INDEX, len(bars) - 2)}
    fit = None
    fitted_at = 0
    for t in range(201 + min_train, len(bars) - 2):
        if fit is None or t - fitted_at >= retrain_every:
            train_rows = range(WARMUP_INDEX, t - 2)
            fit = _fit(
                [features[j] for j in train_rows],
                [_simple_return(bars[j + 2]["open"], bars[j + 1]["open"]) for j in train_rows],
                ridge_alpha,
            )
            fit.update({
                "prediction_date": bars[t]["date"],
                "max_train_label_date": bars[t - 1]["date"],
                "train_count": len(train_rows),
            })
            fitted_at = t
            fits.append(fit)
        entry, exit_bar = bars[t + 1], bars[t + 2]
        predictions.append({
            "prediction_date": bars[t]["date"],
            "entry_date": entry["date"],
            "exit_date": exit_bar["date"],
            "entry_open": entry["open"],
            "exit_open": exit_bar["open"],
            "max_train_label_date": fit["max_train_label_date"],
            "train_count": fit["train_count"],
            "baseline_prediction": fit["training_mean"],
            "prediction": _predict(fit, features[t]),
            "actual_return": _simple_return(exit_bar["open"], entry["open"]),
        })
    fee = cost_bps / 10_000
    positions = [int(row["prediction"] > 2 * fee) for row in predictions]
    strategy, strategy_rows = _portfolio(predictions, positions, fee)
    benchmark, benchmark_rows = _portfolio(predictions, [1] * len(predictions), fee)
    for prediction, strategy_row, benchmark_row in zip(predictions, strategy_rows, benchmark_rows):
        prediction.update(strategy_row)
        prediction["buy_hold_net_return"] = benchmark_row["net_return"]
        prediction["buy_hold_gross_return"] = benchmark_row["gross_return"]
    errors = [row["actual_return"] - row["prediction"] for row in predictions]
    baseline_errors = [row["actual_return"] - row["baseline_prediction"] for row in predictions]
    baseline_sse = math.fsum(error * error for error in baseline_errors)
    return {
        "model_status": "experimental_unvalidated",
        "adjustment": adjustment,
        "configuration": {
            "min_train": min_train, "retrain_every": retrain_every,
            "cost_bps": cost_bps, "ridge_alpha": ridge_alpha, "max_rows": 4000,
        },
        "summary": {
            "samples": len(predictions), "strategy": strategy, "buy_hold": benchmark,
            "mae": fmean(abs(error) for error in errors),
            "baseline_mae": fmean(abs(error) for error in baseline_errors),
            "r2_oos_vs_training_mean": (
                1 - math.fsum(error * error for error in errors) / baseline_sse
                if baseline_sse else None
            ),
        },
        "predictions": predictions,
        "fits": fits,
        "methodology": {
            "target": "open[t+2] / open[t+1] - 1; signal observed after completed close[t]",
            "purge": "training label end j+2 strictly before prediction row t; j <= t-3",
            "validation": "chronological expanding training; no random cross-validation or tuning",
            "features": {
                "return5": "close[t] / close[t-5] - 1",
                "return21": "close[t] / close[t-21] - 1",
                "return63": "close[t] / close[t-63] - 1",
                "vol20": "sample standard deviation of last 20 close-to-close simple returns",
                "close_ma200_gap": "close[t] / mean(close[t-199:t+1]) - 1",
            },
            "scaling": "training-only mean and population standard deviation; constant scale=1",
            "ridge": "sum squared errors + fixed ridge_alpha * sum(beta^2); unpenalized intercept",
            "roundtrip_threshold": "prediction > 2 * cost_bps / 10000",
            "fees": "per-side wealth-proportional fees on position changes and final liquidation",
            "benchmark": "buy-and-hold over identical entry/exit dates with identical per-side fees",
            "adjusted_close_policy": "validated if present but ignored; supplied OHLC is the sole price basis",
            "annualization": "252 observations/year assumed, riskfree=0; sample standard deviation",
            "max_drawdown": "maximum fractional peak-to-trough loss at OOS period ends, including initial wealth=1",
            "trade_count": "one-sided position changes including final liquidation; binary long/cash",
            "turnover": "sum absolute position changes including final liquidation, not annualized",
            "total_cost": "sum actual fee debits in units of initial wealth=1, not currency",
            "total_cost_rate": "sum per-side fee fractions (fee * turnover), not compounded wealth loss",
            "r2_oos_vs_training_mean": "1 - model squared errors / squared errors of each fold training-mean forecasts",
            "undefined_metrics": "R2 is null for zero baseline error; Sharpe null for fewer than two samples or zero volatility",
        },
        "data_requirements": [
            "Completed daily OHLCV bars for one asset, venue, currency and consistent price units.",
            "Unique increasing YYYY-MM-DD dates; no sorting, interpolation or silent truncation.",
            "Caller must attest all OHLC are consistently split-normalized or all are raw.",
            "Corporate-action provenance and a complete session calendar must be checked upstream.",
        ],
        "limitations": [
            "Experimental, unvalidated research baseline; no predictive edge or future returns established.",
            "Not a replication of NBER Working Paper 25398 and not an HFT/latency model.",
            "Hypothetical next-open fills, fractional full-wealth positions; no liquidity, impact or spread model beyond the supplied fee assumption.",
            "Raw prices may contain split jumps; cash earns zero; dividends, taxes and financing are excluded.",
            "The 2*fee signal threshold is a roundtrip approximation, not an exact compounded breakeven.",
            "Repeated inspection or parameter selection on this report introduces selection bias.",
        ],
    }
