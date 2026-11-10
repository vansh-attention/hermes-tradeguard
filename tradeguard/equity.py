"""Dependency-free, read-only daily stock/ETF research, never execution.

Contract and chronology
-----------------------
``analyze_snapshot(snapshot, as_of=None)`` uses the current UTC date only for
None; explicit dates must be canonical YYYY-MM-DD. Metadata keys are symbol,
asset_type (stock/etf), currency, source, retrieved_at (timezone-aware ISO),
data_mode (historical/fixture/delayed/live), adjustment (raw/split/total_return),
and interval (1d only). Bars must be increasing, unique dated OHLCV dicts;
OHLC > 0, volume >= 0, booleans/strings/NaN/Inf are not numbers. At most 10,000
bars/holdings are accepted. Nonzero numeric magnitudes outside [1e-100, 1e100]
are rejected defensively. No sorting, filling, FX conversion, or synonym guesses.
Provider warnings are preserved as caveats, not treated as instructions.

Fundamentals use only the canonical FUNDAMENTAL_FIELDS below plus source,
filed_at, period_end, currency and optional period_start/symbol/warnings. Require
period_end <= filed_at <= as_of and matching symbol/currency. A future or
malformed statement invalidates the analysis; it is never used. Data supplied
for ETFs is not interpreted as the ETF entity's earnings. Source/filing dates
establish eligibility, NOT archival vintage: later downloads are warned about,
and bars dated after their retrieval UTC date are rejected. Exchange/session
calendars, publication times within a day, and revisions cannot be certified.

Price formulas and bases
------------------------
All windows count observations, not calendar days. C is adjusted_close when
present on EVERY bar, otherwise close on the explicitly declared OHLC basis.
SMA(n) = mean(last n C); EMA(n) seeds with first-n SMA, then alpha=2/(n+1).
MACD = EMA12-EMA26 (no signal line). Wilder14 seeds first 14 changes/ranges,
then A[t]=(13*A[t-1]+x[t])/14. RSI=100-100/(1+avg_gain/avg_loss), with flat=50
and no losses=100. ATR uses TR=max(H-L,abs(H-prevC),abs(L-prevC)), excluding
the first unpaired bar; split-adjusted close scales each bar's H/L by C/close.
Total-return adjusted-close/OHLC mismatches leave ATR unavailable: dividend
adjustment is not assumed equivalent to split-adjusting ranges. Dollar volume
always means mean(last20 raw supplied close*volume), without rescaling volume.
vol20 = SAMPLE stdev(last20 simple daily returns)*sqrt(252), needing 21 bars.
max_drawdown = min(C/running_peak-1) over the whole supplied history.
return(n)=C[-1]/C[-n-1]-1; momentum12_1=C[-22]/C[-253]-1 requires 253 bars.
Split/raw returns exclude unprovided cash distributions; they are not total
returns. No indicator is a forecast, and overlapping indicators are correlated.

Fundamental and ETF formulas
----------------------------
Earnings yield=net_income/market_cap; FCF yield=(operating_cash_flow-capex)/
market_cap. Capex is a nonnegative cash OUTFLOW, never silently sign-flipped.
ROE=NI/ending equity; ROA=NI/ending assets; growth=revenue/revenue_prev-1;
operating_margin=operating_income/revenue; gross_margin=gross_profit/revenue;
net debt/assets=(total_debt-cash)/assets; interest coverage=operating_income/interest;
accruals=(NI-CFO)/mean(assets,assets_prev). Every denominator must be positive;
accruals require both asset observations positive. Missing inputs stay None.
These are single as-reported-period ratios, NEVER implicit TTM or annualized.
Optional period_start must precede/equal period_end. annual_duration_verified
is True only for an explicit inclusive duration of 330..380 days, otherwise
False; verified duration still does not create TTM. Market-cap timing remains an
upstream responsibility; no current quote is silently used for old filings.
The top research-candidate label requires explicit annual duration, symbol binding,
and market_cap_as_of within 7 days of the last price observation when cap is used.

ETF input is snapshot['etf']: source, as_of, decimal expense_ratio, nav,
nav_date, and holdings=[{symbol,weight decimal fraction}]. Optional symbol and
currency must match. NAV premium uses UNADJUSTED last close/nav-1 ONLY on the
same date. Holdings coverage=sum(weights), observed HHI=sum(weight**2), and
observed top10=sum(10 largest weights). No renormalization: full HHI/top10 are
None unless coverage is 1 within 1e-6. They are lower bounds for partial lists.
Optional etf.benchmark_returns is a list of {date,return} with every date exactly
matching bars[1:], simple returns > -1 on the SAME return basis as the fund.
Tracking error is sample stdev(fund return-benchmark return)*sqrt(252) over
all aligned observations (minimum20); relative return(n)=fund wealth/benchmark
compounded wealth-1. Benchmark absence does not inflate structure coverage.

Auditable policy choices, NOT source-validated thresholds
--------------------------------------------------------
Each strategy has a fixed 100-point denominator; missing checks earn zero.
Trend weights: price/SMA200>1 (25), SMA50/SMA200>1 (20), momentum12_1>0 (20),
return63>0 (15), vol20<=.40 (10), dollar_volume20>=1m quote-currency units (10).
Strict positivity uses numerical tolerances 1e-9 for price ratios and 1e-12
for returns. Value+quality weights: earnings_yield>=.05 (15), FCF>=.04 (15),
ROE>=.12 (15), ROA>=.05 (10), growth>0 (10), operating margin>=.10 (10), net
 debt/assets<=.40 (10), interest coverage>=3 (5), accruals<=.05 (10).
ETF structure: expense<=.0025 (30), abs(NAV premium)<=.005 (20), full HHI<=.10
(20), full top10<=.60 (20), liquidity>=1m (10). Mean-reversion: RSI20..35 (40),
price/SMA20=.90..98 (20), price>=SMA200 (20), vol<=.35 (10), liquidity (10),
bounded to 60 points and excluded from the aggregate; this is not a timing rule.

Aggregate = .4*trend + .6*value_quality (stock) or .6*ETF_structure (ETF).
Evidence coverage uses the same .4/.6 weights on fixed metric-availability
fractions; it is NOT a win probability. Candidate requires score>=70 and ALL
applicable core metrics available. Otherwise score>=45 gives WATCHLIST,
else AVOID_OR_WAIT; coverage<.70 gives ABSTAIN. WATCHLIST scores are capped at69,
coverage abstentions at49; uncapped weighted evidence remains diagnostic_score.
Hard blockers zero the recommendation score and abstain every strategy:
fixture mode, fewer than253 bars, price age>7 calendar days, a daily gap>7 days,
fundamental filing/period age>548 days, or ETF metadata age>90 days. Missing
fundamentals/ETF information cannot become safe defaults. Raw historical data
and user-provided provenance are not verified; scores remain uncalibrated.

Concepts are source-inspired (French factor/momentum definitions; SEC filings;
investor.gov ETF fees), independently implemented. Those sources do not validate
these weights, thresholds, recommendations, or any trading performance.
Output always reports research_only=True and model_status=unvalidated_heuristic.
There is no network, order placement, position sizing, trained model, or backtest.
Retrieval-day daily bars require source-supplied exchange_timezone and a
session_close_at clock on the last bar's exchange date, no later than retrieval.
Without a zone, use the earliest civil date conservatively. Finalization is
validated caller evidence, not independent exchange-calendar certification.
"""

import math
import statistics
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .indicators import ema as _ema, technical as _technical, wilder as _wilder


MAX_BARS = 10_000
FUNDAMENTAL_FIELDS = (
    "revenue", "revenue_prev", "net_income", "operating_income", "gross_profit",
    "operating_cash_flow", "capex", "assets", "assets_prev", "equity", "total_debt",
    "cash", "interest_expense", "market_cap",
)


def _strategy(horizon, specifications, cap=100):
    """Missing checks earn zero; the denominator never shrinks."""
    checks, bullish, bearish = [], [], []
    for name, weight, value, low, high in specifications:
        passed = None if value is None else low <= value <= high
        rule = f"{low} <= {name} <= {high}"
        checks.append({"criterion": name, "weight": weight, "value": value,
                       "passed": passed, "rule": rule})
        if passed:
            bullish.append(f"Supported: {rule}")
        else:
            bearish.append(f"{'Missing evidence' if passed is None else 'Not supported'}: {rule}")
    earned = sum(check["weight"] for check in checks if check["passed"])
    observed = sum(check["weight"] for check in checks if check["passed"] is not None)
    score = min(cap, earned)
    return {"horizon": horizon, "score": score, "max_score": cap,
            "weight_denominator": 100, "evidence_coverage": observed / 100,
            "checks": checks, "bullish_reasons": bullish, "bearish_reasons": bearish,
            "action": ("ABSTAIN" if observed < 70 else
                       "RESEARCH_CANDIDATE" if score >= 70 and observed == 100 else
                       "WATCHLIST" if score >= 45 else "AVOID_OR_WAIT"),
            "hypothesis_only": True}


def _strategies(result, snapshot, bars):
    t = result["metrics"]["technical"]
    close = bars[-1].get("adjusted_close", bars[-1]["close"])
    infinity = float("inf")
    strategies = {
        "trend_following": _strategy("technical_swing_weeks_to_months", [
            ("price_to_sma200", 25, _ratio(close, t["sma200"]), 1.000000001, infinity),
            ("sma50_to_sma200", 20, _ratio(t["sma50"], t["sma200"]), 1.000000001, infinity),
            ("momentum12_1", 20, t["momentum12_1"], 1e-12, infinity),
            ("return63", 15, t["return63"], 1e-12, infinity),
            ("vol20", 10, t["vol20"], 0, .40),
            ("dollar_volume20", 10, t["dollar_volume20"], 1_000_000, infinity),
        ]),
        "mean_reversion": _strategy("technical_swing_days_to_weeks", [
            ("rsi14", 40, t["rsi14"], 20, 35),
            ("price_to_sma20", 20, _ratio(close, t["sma20"]), .90, .98),
            ("price_to_sma200", 20, _ratio(close, t["sma200"]), 1, infinity),
            ("vol20", 10, t["vol20"], 0, .35),
            ("dollar_volume20", 10, t["dollar_volume20"], 1_000_000, infinity),
        ], cap=60),
    }
    if snapshot["asset_type"] == "stock":
        f = result["metrics"]["fundamentals"]
        strategies["value_quality"] = _strategy("fundamental_investing_years", [
            ("earnings_yield", 15, f["earnings_yield"], .05, infinity),
            ("fcf_yield", 15, f["fcf_yield"], .04, infinity),
            ("roe", 15, f["roe"], .12, infinity),
            ("roa", 10, f["roa"], .05, infinity),
            ("revenue_growth", 10, f["revenue_growth"], 1e-12, infinity),
            ("operating_margin", 10, f["operating_margin"], .10, infinity),
            ("net_debt_to_assets", 10, f["net_debt_to_assets"], -infinity, .40),
            ("interest_coverage", 5, f["interest_coverage"], 3, infinity),
            ("accrual_ratio", 10, f["accrual_ratio"], -infinity, .05),
        ])
        component, strategy = "fundamentals", "value_quality"
    else:
        e = result["metrics"]["etf"]
        premium = e["nav_premium"]
        strategies["etf_structure"] = _strategy("etf_costs_and_structure_long_term", [
            ("expense_ratio", 30, e["expense_ratio"], 0, .0025),
            ("absolute_nav_premium", 20, abs(premium) if premium is not None else None, 0, .005),
            ("hhi", 20, e["hhi"], 0, .10),
            ("top10_weight", 20, e["top10_weight"], 0, .60),
            ("dollar_volume20", 10, t["dollar_volume20"], 1_000_000, infinity),
        ])
        strategies["value_quality"] = {"status": "not_applicable",
                                       "reason": "Company earnings do not value the ETF entity"}
        component, strategy = "etf", "etf_structure"
    result["strategies"] = strategies
    coverage = (.4 * result["coverage"]["technical"]["fraction"]
                + .6 * result["coverage"][component]["fraction"])
    score = round(.4 * strategies["trend_following"]["score"] + .6 * strategies[strategy]["score"], 2)
    complete = (result["coverage"]["technical"]["fraction"] == 1
                and result["coverage"][component]["fraction"] == 1)
    action = ("ABSTAIN" if coverage < .7 or len(bars) < 253 else
              "RESEARCH_CANDIDATE" if score >= 70 and complete else
              "WATCHLIST" if score >= 45 else "AVOID_OR_WAIT")
    result["recommendation"] = {
        "action": action, "score": score, "evidence_coverage": round(coverage, 6),
        "score_kind": "heuristic_uncalibrated_not_probability",
        "weights": {"trend_following": .4, strategy: .6},
        "weight_denominator": 1.0,
    }
    result["confidence"].update({"coverage": round(coverage, 6),
        "label": "high_evidence_coverage" if complete else
                 "partial_evidence_coverage" if coverage >= .7 else "insufficient"})


def _ratio(numerator, denominator):
    return (numerator / denominator if numerator is not None
            and denominator is not None and denominator > 0 else None)


def _apply_evidence_gates(result, snapshot, bars, today):
    blockers = []
    limitations = []
    if len(bars) < 253:
        blockers.append("Insufficient daily history: 253 bars required for research recommendation")
    if snapshot["data_mode"] == "fixture":
        blockers.append("Fixture/synthetic data cannot support a recommendation")
    age = (today - _day(bars[-1]["date"])).days
    result["coverage"]["technical"]["age_days"] = age
    if age > 7:
        blockers.append("Stale price data: last bar older than 7 calendar days")
    gaps = [(_day(bars[i]["date"]) - _day(bars[i - 1]["date"])).days
            for i in range(1, len(bars))]
    if gaps and max(gaps) > 7:
        blockers.append("Sparse daily history: gap exceeds 7 calendar days; no calendar repair")
    if snapshot["asset_type"] == "stock" and snapshot.get("fundamentals"):
        f = snapshot["fundamentals"]
        missing = [name for name, value in result["metrics"]["fundamentals"].items() if value is None]
        if missing:
            limitations.append("Incomplete fundamental metric evidence: " + ", ".join(missing))
        if not result["coverage"]["fundamentals"]["annual_duration_verified"]:
            limitations.append("Value/quality policy requires an explicit verified annual reporting duration")
        if f.get("symbol") != snapshot["symbol"]:
            limitations.append("Fundamental issuer identity is not explicitly bound to the price symbol")
        if f.get("market_cap") is not None:
            cap_day = f.get("market_cap_as_of")
            if cap_day is None or abs((_day(bars[-1]["date"]) - _day(cap_day)).days) > 7:
                limitations.append("Valuation market cap needs an observation date within 7 days of the price cutoff")
        age = (today - _day(f["period_end"])).days
        result["coverage"]["fundamentals"]["age_days"] = age
        if age > 548 or (today - _day(f["filed_at"])).days > 548:
            blockers.append("Stale annual/as-reported fundamentals: older than 548 calendar days")
    if snapshot["asset_type"] == "etf" and snapshot.get("etf"):
        e = snapshot["etf"]
        missing = [name for name, value in result["metrics"]["etf"].items() if value is None]
        if missing:
            limitations.append("Incomplete ETF metric evidence: " + ", ".join(missing))
        if e.get("symbol") != snapshot["symbol"] or e.get("currency") != snapshot["currency"]:
            limitations.append("ETF metadata must explicitly bind the same symbol and currency before a candidate label")
        age = (today - _day(snapshot["etf"]["as_of"])).days
        result["coverage"]["etf"]["age_days"] = age
        if age > 90:
            blockers.append("Stale ETF metadata: as_of older than 90 calendar days")
    recommendation = result["recommendation"]
    recommendation.update(strong_recommendation_eligible=False,
        validation_status="heuristic_only_not_performance_validated", evidence_limitations=limitations)
    recommendation["diagnostic_score"] = recommendation["score"]
    recommendation["blockers"] = blockers
    if limitations:
        result["warnings"].extend(limitations)
        if recommendation["action"] == "RESEARCH_CANDIDATE":
            recommendation["action"] = "WATCHLIST"
        if result["confidence"]["label"] == "high_evidence_coverage":
            result["confidence"]["label"] = "complete_metrics_incomplete_provenance"
        name = "value_quality" if snapshot["asset_type"] == "stock" else "etf_structure"
        strategy = result["strategies"][name]
        strategy["bearish_reasons"].extend(limitations)
        if strategy["action"] == "RESEARCH_CANDIDATE":
            strategy.update(action="WATCHLIST", diagnostic_score=strategy["score"], score=69)
    if recommendation["action"] == "WATCHLIST":
        recommendation["score"] = min(recommendation["score"], 69)
    elif recommendation["action"] == "ABSTAIN":
        recommendation["score"] = min(recommendation["score"], 49)
    if blockers:
        recommendation.update(action="ABSTAIN", score=0)
        result["warnings"].extend(blockers)
        result["confidence"]["label"] = "unusable_evidence"
        for strategy in result["strategies"].values():
            if "action" in strategy:
                strategy["action"] = "ABSTAIN"
                strategy["bearish_reasons"].extend(blockers)


def _etf_metrics(etf, bars, warnings):
    e = etf or {}
    holdings = e.get("holdings")
    weights = [holding["weight"] for holding in holdings] if holdings else []
    coverage = math.fsum(weights) if weights else None
    full = (coverage is not None and math.isclose(coverage, 1, abs_tol=1e-6)
            and e.get("holdings_complete") is not False)
    hhi = math.fsum(weight ** 2 for weight in weights) if weights else None
    top10 = math.fsum(sorted(weights, reverse=True)[:10]) if weights else None
    premium = None
    if e.get("nav") is not None and e.get("nav_date") == bars[-1]["date"]:
        premium = bars[-1]["close"] / e["nav"] - 1
    elif e.get("nav") is not None:
        warnings.append("NAV premium unavailable: nav_date does not equal last close date")
    if weights and not full:
        warnings.append("Partial holdings: observed HHI/top10 are lower bounds, not full concentration")
    return {"expense_ratio": e.get("expense_ratio"), "nav_premium": premium,
            "holdings_weight_coverage": coverage, "hhi_observed": hhi,
            "top10_weight_observed": top10, "hhi": hhi if full else None,
            "top10_weight": top10 if full else None}


def _benchmark_metrics(etf, bars):
    benchmark = (etf or {}).get("benchmark_returns")
    metrics = {"tracking_error": None, "relative_return21": None,
               "relative_return63": None, "relative_return252": None}
    if not benchmark:
        return metrics
    closes = [bar.get("adjusted_close", bar["close"]) for bar in bars]
    returns = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    differences = [value - ref["return"] for value, ref in zip(returns, benchmark)]
    if len(differences) >= 20:
        metrics["tracking_error"] = statistics.stdev(differences) * math.sqrt(252)
    for period in (21, 63, 252):
        if len(benchmark) >= period:
            benchmark_wealth = math.prod(1 + item["return"] for item in benchmark[-period:])
            if not math.isfinite(benchmark_wealth) or benchmark_wealth <= 0:
                raise ArithmeticError("benchmark compounded wealth outside numeric range")
            metrics[f"relative_return{period}"] = (
                (closes[-1] / closes[-period - 1]) / benchmark_wealth - 1)
    if any(value is not None and not math.isfinite(value) for value in metrics.values()):
        raise ArithmeticError("benchmark derived metric outside numeric range")
    return metrics


def _fundamental_metrics(fundamentals):
    f = fundamentals or {}
    v = {field: f.get(field) for field in FUNDAMENTAL_FIELDS}
    fcf = (v["operating_cash_flow"] - v["capex"]
           if v["operating_cash_flow"] is not None and v["capex"] is not None else None)
    net_debt = (v["total_debt"] - v["cash"]
                if v["total_debt"] is not None and v["cash"] is not None else None)
    accruals = (v["net_income"] - v["operating_cash_flow"]
                if v["net_income"] is not None and v["operating_cash_flow"] is not None else None)
    average_assets = ((v["assets"] + v["assets_prev"]) / 2
                      if v["assets"] is not None and v["assets"] > 0
                      and v["assets_prev"] is not None and v["assets_prev"] > 0 else None)
    growth = _ratio(v["revenue"], v["revenue_prev"])
    return {
        "earnings_yield": _ratio(v["net_income"], v["market_cap"]),
        "fcf_yield": _ratio(fcf, v["market_cap"]),
        "roe": _ratio(v["net_income"], v["equity"]),
        "roa": _ratio(v["net_income"], v["assets"]),
        "revenue_growth": growth - 1 if growth is not None else None,
        "operating_margin": _ratio(v["operating_income"], v["revenue"]),
        "gross_margin": _ratio(v["gross_profit"], v["revenue"]),
        "net_debt_to_assets": _ratio(net_debt, v["assets"]),
        "interest_coverage": _ratio(v["operating_income"], v["interest_expense"]),
        "accrual_ratio": _ratio(accruals, average_assets),
    }


def _coverage(metrics):
    available = sum(value is not None for value in metrics.values())
    total = len(metrics)
    return {"available": available, "total": total,
            "fraction": available / total if total else 0,
            "status": "complete" if available == total and total else "partial"}


def _day(value):
    if not isinstance(value, str):
        raise ValueError("expected YYYY-MM-DD")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("expected YYYY-MM-DD")
    return parsed


def _number(value):
    # Reject bool and extreme magnitudes rather than accepting coercible strings.
    return (type(value) in (int, float) and (value == 0 or 1e-100 <= abs(value) <= 1e100)
            and math.isfinite(value))


def _validate_fundamentals(snapshot, today, errors):
    f = snapshot.get("fundamentals")
    if f is None:
        return
    if not isinstance(f, dict):
        errors.append("fundamentals must be a dict")
        return
    if "symbol" in f and f["symbol"] != snapshot.get("symbol"):
        errors.append("fundamentals.symbol must match snapshot symbol exactly")
    if not isinstance(f.get("source"), str) or not f["source"].strip():
        errors.append("fundamentals.source required")
    if f.get("currency") != snapshot.get("currency"):
        errors.append("fundamentals.currency must match price currency; no FX assumptions")
    try:
        filed, period = _day(f.get("filed_at")), _day(f.get("period_end"))
        if filed > today:
            errors.append("fundamentals.filed_at is future; fundamentals ignored")
        if period > filed:
            errors.append("fundamentals.period_end exceeds filed_at; fundamentals ignored")
    except (TypeError, ValueError):
        errors.append("fundamentals filed_at and period_end require YYYY-MM-DD")
    if f.get("period_start") is not None:
        try:
            if _day(f["period_start"]) > _day(f.get("period_end")):
                errors.append("fundamentals.period_start exceeds period_end")
        except (TypeError, ValueError):
            errors.append("fundamentals.period_start requires YYYY-MM-DD")
    if "market_cap_as_of" in f:
        try:
            if _day(f["market_cap_as_of"]) > today:
                errors.append("fundamentals.market_cap_as_of exceeds analysis cutoff")
        except (TypeError, ValueError):
            errors.append("fundamentals.market_cap_as_of requires YYYY-MM-DD")
    nonnegative = {"capex", "total_debt", "cash", "interest_expense", "market_cap"}
    for field in FUNDAMENTAL_FIELDS:
        value = f.get(field)
        if value is not None and (not _number(value) or
                                  (field in nonnegative and value < 0)):
            errors.append(f"fundamentals.{field} invalid finite numeric value")


def _validate_etf(snapshot, today, errors):
    e = snapshot.get("etf")
    if e is None:
        return
    if not isinstance(e, dict):
        errors.append("etf must be a dict")
        return
    if "symbol" in e and e["symbol"] != snapshot.get("symbol"):
        errors.append("etf.symbol must match snapshot symbol exactly")
    if not isinstance(e.get("source"), str) or not e["source"].strip():
        errors.append("etf.source required")
    if "currency" in e and e["currency"] != snapshot.get("currency"):
        errors.append("etf.currency must match price currency")
    if "holdings_complete" in e and type(e["holdings_complete"]) is not bool:
        errors.append("etf.holdings_complete must be an explicit boolean")
    try:
        metadata_day = _day(e.get("as_of"))
        if metadata_day > today:
            errors.append("etf.as_of is future; metadata ignored")
    except (TypeError, ValueError):
        errors.append("etf.as_of requires YYYY-MM-DD")
    for field in ("expense_ratio", "nav"):
        value = e.get(field)
        if value is not None and (not _number(value) or
                                  (not 0 <= value <= 1 if field == "expense_ratio" else value <= 0)):
            errors.append(f"etf.{field} invalid; expense_ratio is a decimal fraction, nav positive")
    if e.get("nav") is not None or "nav_date" in e:
        try:
            if _day(e.get("nav_date")) > today:
                errors.append("etf.nav_date is future")
        except (TypeError, ValueError):
            errors.append("etf.nav_date requires YYYY-MM-DD")
    holdings = e.get("holdings")
    if holdings is None:
        return
    if not isinstance(holdings, list) or len(holdings) > MAX_BARS:
        errors.append("etf.holdings must be a list with max 10000 items")
        return
    seen, weights = set(), []
    for holding in holdings:
        if not isinstance(holding, dict):
            errors.append("etf.holdings items must be dicts")
            break
        symbol, weight = holding.get("symbol"), holding.get("weight")
        if not isinstance(symbol, str) or not symbol.strip():
            errors.append("etf.holdings.symbol must be nonempty")
        elif symbol in seen:
            errors.append("etf.holdings duplicate symbol")
        else:
            seen.add(symbol)
        if not _number(weight) or not 0 <= weight <= 1:
            errors.append("etf.holdings.weight must be a decimal fraction in [0,1]")
        else:
            weights.append(weight)
    if math.fsum(weights) > 1 + 1e-6:
        errors.append("etf.holdings total weight exceeds 1")


def _validate_benchmark(snapshot, bars, errors):
    etf = snapshot.get("etf")
    if not isinstance(etf, dict) or etf.get("benchmark_returns") is None:
        return
    benchmark = etf["benchmark_returns"]
    if not isinstance(benchmark, list) or len(benchmark) != max(0, len(bars) - 1):
        errors.append("etf.benchmark_returns must align one-to-one with bars[1:] dates")
        return
    for bar, item in zip(bars[1:], benchmark):
        if (not isinstance(item, dict) or not isinstance(bar, dict)
                or item.get("date") != bar.get("date")):
            errors.append("etf.benchmark_returns unmatched date or non-dict item")
            break
        value = item.get("return")
        if not _number(value) or value <= -1:
            errors.append("etf.benchmark_returns return must be finite numeric > -1")
            break


def _provider_warnings(snapshot, result):
    groups = [("provider_warnings", snapshot.get("provider_warnings"))]
    for name in ("fundamentals", "etf"):
        if isinstance(snapshot.get(name), dict):
            groups.append((f"{name}.warnings", snapshot[name].get("warnings")))
    for name, warnings in groups:
        if warnings is None:
            continue
        if (not isinstance(warnings, list) or len(warnings) > 1000
                or any(not isinstance(warning, str) for warning in warnings)):
            result["validation_errors"].append(f"{name} must be a list of max 1000 strings")
        else:
            result["warnings"].extend(warnings)


def _validate_session_finalization(snapshot, bars, retrieved, errors):
    """A declared daily interval is not evidence its final bar is complete.

    Earlier exchange dates are conservative completed-session candidates. For
    retrieval-day bars require source-supplied exchange zone and final close clock,
    validate clock ordering and last-bar date. This is an attestation, not calendar
    or feed certification; source provenance remains the caller's responsibility.
    """
    zone_name = snapshot.get("exchange_timezone")
    try:
        # Earliest civil date is conservative when an exchange zone is absent.
        zone = ZoneInfo(zone_name if isinstance(zone_name, str) else "Etc/GMT+12")
        retrieval_day = retrieved.astimezone(zone).date()
        last_day = _day(bars[-1]["date"])
        close_value = snapshot.get("session_close_at")
        if close_value is not None:
            if not isinstance(zone_name, str) or not isinstance(close_value, str) or "T" not in close_value:
                raise ValueError("session close requires exchange timezone and an ISO clock")
            close_clock = datetime.fromisoformat(close_value.replace("Z", "+00:00"))
            if close_clock.tzinfo is None or close_clock > retrieved:
                raise ValueError("session_close_at must be timezone-aware and no later than retrieval")
            if close_clock.astimezone(zone).date() != last_day:
                raise ValueError("session_close_at does not match last bar's exchange date")
        elif last_day >= retrieval_day:
            raise ValueError("retrieval-day daily bar requires explicit completed-session close evidence")
    except (ValueError, TypeError, ZoneInfoNotFoundError) as exc:
        errors.append(f"session finalization invalid: {exc}")


def _validate(snapshot, today, errors):
    if not isinstance(snapshot, dict):
        errors.append("snapshot must be a dict")
        return []
    for field in ("symbol", "currency", "source"):
        if not isinstance(snapshot.get(field), str) or not snapshot[field].strip():
            errors.append(f"{field} must be a nonempty string")
    for field, allowed in (
        ("asset_type", ("stock", "etf")), ("interval", ("1d",)),
        ("data_mode", ("historical", "fixture", "delayed", "live")),
        ("adjustment", ("raw", "split", "total_return")),
    ):
        if snapshot.get(field) not in allowed:
            errors.append(f"{field} must be one of {allowed}")
    retrieved_day = None
    parsed = None
    try:
        timestamp = snapshot.get("retrieved_at")
        if not isinstance(timestamp, str) or "T" not in timestamp:
            raise ValueError("timestamp required")
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
        retrieved_day = parsed.astimezone(timezone.utc).date()
    except (TypeError, ValueError):
        errors.append("retrieved_at must be an ISO timestamp with timezone")
    bars = snapshot.get("bars")
    if not isinstance(bars, list) or not bars:
        errors.append("bars must be a nonempty list")
        return []
    if len(bars) > MAX_BARS:
        errors.append("bars exceeds max 10000")
        return []
    previous = None
    adjusted_count = 0
    for i, bar in enumerate(bars):
        prefix = f"bars[{i}]"
        if not isinstance(bar, dict):
            errors.append(f"{prefix} must be a dict")
            break
        try:
            day = _day(bar.get("date"))
            if day > today:
                errors.append(f"{prefix}.date is future to as_of")
            if retrieved_day is not None and day > retrieved_day:
                errors.append(f"{prefix}.date exceeds retrieved_at UTC date")
            if previous is not None and day <= previous:
                errors.append(f"{prefix}.date duplicate or nonmonotonic")
            previous = day
        except (TypeError, ValueError):
            errors.append(f"{prefix}.date must be YYYY-MM-DD")
        valid = True
        for field in ("open", "high", "low", "close", "volume"):
            value = bar.get(field)
            if not _number(value) or (value < 0 if field == "volume" else value <= 0):
                errors.append(f"{prefix}.{field} invalid finite numeric value")
                valid = False
        if valid and not (bar["low"] <= min(bar["open"], bar["close"])
                          <= max(bar["open"], bar["close"]) <= bar["high"]):
            errors.append(f"{prefix} crossed OHLC")
        if "adjusted_close" in bar and (not _number(bar["adjusted_close"])
                                        or bar["adjusted_close"] <= 0):
            errors.append(f"{prefix}.adjusted_close invalid")
        if "adjusted_close" in bar:
            adjusted_count += 1
            if snapshot.get("adjustment") == "raw" and bar["adjusted_close"] != bar.get("close"):
                errors.append(f"{prefix}.adjusted_close conflicts with raw adjustment")
        if len(errors) > 30:
            errors.append("validation truncated after first 30 errors")
            break
    if adjusted_count not in (0, len(bars)):
        errors.append("adjusted_close must be present for all bars or none")
    if not errors and parsed is not None:
        _validate_session_finalization(snapshot, bars, parsed, errors)
        for window in (bars, bars[-253:], bars[-21:]):
            gaps = [(_day(window[i]["date"]) - _day(window[i - 1]["date"])).days
                    for i in range(1, len(window))]
            sparse = len(gaps) >= 10 and (statistics.median(gaps) > 1 or statistics.mean(gaps) > 2)
            if gaps and (max(gaps) > 7 or sparse):
                errors.append("Sparse/non-daily session history; cannot annualize by 252 daily observations")
                break
    return bars


def _analyze_snapshot(snapshot: dict, as_of: str | None = None) -> dict:
    """Return auditable research, never an order or a position size."""
    result = {
        "as_of": datetime.now(timezone.utc).date().isoformat() if as_of is None else as_of,
        "symbol": None, "asset_type": None, "currency": None,
        "research_only": True,
        "model_status": "unvalidated_heuristic",
        "recommendation": {"action": "ABSTAIN", "score": 0, "evidence_coverage": 0,
                           "score_kind": "heuristic_uncalibrated_not_probability",
                           "blockers": [], "diagnostic_score": 0, "evidence_limitations": [],
                           "strong_recommendation_eligible": False,
                           "validation_status": "heuristic_only_not_performance_validated"},
        "confidence": {"label": "insufficient", "coverage": 0.0,
                       "meaning": "evidence_coverage_not_win_probability"},
        "validation_errors": [], "missing_data": [], "warnings": [],
        "metrics": {"technical": {}, "fundamental": {}, "fundamentals": {}, "etf": {}},
        "sources": {}, "coverage": {}, "strategies": {},
    }
    try:
        today = _day(result["as_of"])
    except (TypeError, ValueError):
        result["validation_errors"].append("as_of must be YYYY-MM-DD")
        result["as_of"] = None
        return result
    bars = _validate(snapshot, today, result["validation_errors"])
    if isinstance(snapshot, dict):
        _provider_warnings(snapshot, result)
        _validate_fundamentals(snapshot, today, result["validation_errors"])
        _validate_etf(snapshot, today, result["validation_errors"])
        _validate_benchmark(snapshot, bars, result["validation_errors"])
        for key in ("symbol", "asset_type", "currency"):
            result[key] = snapshot.get(key) if isinstance(snapshot.get(key), str) else None
        result["sources"]["prices"] = {
            key: snapshot.get(key) if isinstance(snapshot.get(key), str) else None for key in
            ("source", "retrieved_at", "data_mode", "adjustment", "currency", "interval")
        }
    if not bars:
        result["missing_data"].append("bars")
    if result["validation_errors"]:
        result["recommendation"]["blockers"] = list(result["validation_errors"])
        result["warnings"].append("Input evidence rejected; inspect validation_errors before interpreting any metric")
        return result
    retrieved = datetime.fromisoformat(snapshot["retrieved_at"].replace("Z", "+00:00"))
    if retrieved.astimezone(timezone.utc).date() > today:
        result["warnings"].append("Downloaded after as_of: not verified archival/vintage data")
    technical = _technical(bars, snapshot["adjustment"], result["warnings"])
    result["metrics"]["technical"] = technical
    result["coverage"]["technical"] = _coverage(technical)
    result["missing_data"].extend(f"technical.{name}" for name, value in technical.items()
                                  if value is None)
    fundamentals = snapshot.get("fundamentals")
    if snapshot["asset_type"] == "stock":
        fundamental_metrics = _fundamental_metrics(fundamentals)
        period_start = (fundamentals or {}).get("period_start")
        duration = ((_day(fundamentals["period_end"]) - _day(period_start)).days + 1
                    if period_start is not None else None)
        annual_verified = duration is not None and 330 <= duration <= 380
        result["missing_data"].extend(f"fundamentals.{name}" for name in FUNDAMENTAL_FIELDS
                                      if (fundamentals or {}).get(name) is None)
        result["metrics"]["fundamentals"] = fundamental_metrics
        result["coverage"]["fundamentals"] = {
            **_coverage(fundamental_metrics),
            "period_basis": "as_reported_not_ttm_not_annualized",
            "annual_duration_verified": annual_verified,
            "period_start": period_start, "period_duration_days": duration,
            "period_end": (fundamentals or {}).get("period_end"),
        }
        result["sources"]["fundamentals"] = {
            key: (fundamentals or {}).get(key)
            for key in ("source", "filed_at", "period_start", "period_end", "currency")
        }
        result["missing_data"].extend(
            f"fundamentals.{name}" for name, value in fundamental_metrics.items() if value is None)
        if fundamentals:
            result["warnings"].append(
                ("Annual-duration reporting period verified" if annual_verified else
                 "Reporting duration unverified") +
                ": yields are as-reported, not TTM or annualized")
        result["coverage"]["etf"] = {"status": "not_applicable"}
    else:
        result["coverage"]["fundamentals"] = {"status": "not_applicable"}
        if fundamentals:
            result["warnings"].append("Company fundamentals ignored for ETF entity")
        etf = snapshot.get("etf")
        etf_metrics = _etf_metrics(etf, bars, result["warnings"])
        result["metrics"]["etf"] = etf_metrics
        result["coverage"]["etf"] = _coverage(etf_metrics)
        result["sources"]["etf"] = {
            key: (etf or {}).get(key) for key in ("source", "as_of", "nav_date")
        }
        result["missing_data"].extend(
            f"etf.{name}" for name, value in etf_metrics.items() if value is None)
        try:
            benchmark_metrics = _benchmark_metrics(etf, bars)
        except ArithmeticError:
            error = "etf.benchmark_returns derived arithmetic outside safe finite range"
            result["validation_errors"].append(error)
            result["recommendation"]["blockers"] = [error]
            return result
        result["metrics"]["benchmark"] = benchmark_metrics
        result["coverage"]["benchmark"] = _coverage(benchmark_metrics)
        if not (etf or {}).get("benchmark_returns"):
            result["missing_data"].append("etf.benchmark_returns")
    result["metrics"]["fundamental"] = result["metrics"]["fundamentals"]
    _strategies(result, snapshot, bars)
    _apply_evidence_gates(result, snapshot, bars, today)
    return result


def _buy_recommendation(report: dict) -> dict:
    """Constructive presentation of the SAME capped score, not new alpha.

    Do not use the uncapped diagnostic score or boost it to sound optimistic.
    Abstention is unknown (None), not zero support and never a disguised buy.
    The display thresholds below are policy labels, not calibrated probabilities.
    """
    recommendation = report["recommendation"]
    action, points = recommendation["action"], recommendation["score"]
    usable = (action in {"RESEARCH_CANDIDATE", "WATCHLIST", "AVOID_OR_WAIT"}
              and _number(points) and 0 <= points <= 100)
    score = round(points / 100, 4) if usable else None
    if score is None:
        verdict = "ABSTAIN"
        conclusion = "No reliable buy-interest score yet: resolve the missing, stale or invalid evidence first."
    elif action == "RESEARCH_CANDIDATE":
        verdict = "BUY_RESEARCH_CANDIDATE"
        conclusion = "Favorable research setup worth considering after independent valuation and risk checks; not a validated strong-buy call."
    elif action == "WATCHLIST" and score >= .60:
        verdict = "CONSTRUCTIVE_WATCHLIST"
        conclusion = "Constructive signals make this worth a closer look; keep it on the watchlist while resolving the remaining cautions."
    elif action == "WATCHLIST":
        verdict = "MIXED_WATCHLIST"
        conclusion = "Some encouraging signals, but the overall setup is mixed; seek more confirmation before treating it as a buy."
    else:
        verdict = "WAIT_FOR_BETTER_SETUP"
        conclusion = "Current evidence offers limited buying support; wait for a better-supported setup."
    cautions = list(dict.fromkeys(report.get("validation_errors", [])
        + recommendation.get("blockers", []) + recommendation.get("evidence_limitations", [])))
    return {"score": score, "verdict": verdict, "conclusion": conclusion,
            "score_type": "uncalibrated_buy_interest_not_profit_probability",
            "scale": "0 = weakest heuristic support; 1 = strongest; null = abstain",
            "evidence_coverage": recommendation["evidence_coverage"],
            "strong_buy": False, "cautions": cautions}


def analyze_snapshot(snapshot: dict, as_of: str | None = None) -> dict:
    """Analyze evidence and append a 0..1 buy-interest conclusion LAST.

    The final field is shared by the native plugin and JSON CLI without changing
    scoring weights, freshness/coverage gates, missingness or execution permissions.
    """
    result = _analyze_snapshot(snapshot, as_of=as_of)
    result["buy_recommendation"] = _buy_recommendation(result)
    return result
