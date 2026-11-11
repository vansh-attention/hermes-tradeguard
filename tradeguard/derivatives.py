"""Offline cash-index derivative research, not a provider or execution adapter.

All public snapshot ingress remains fixture/user supplied. No JSON assertion can
promote it to an entitled live feed. Calculations and directional observations
are useful independently of the deliberately unavailable current-entry score.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Context, Decimal, localcontext

SCORE_TYPE = "uncalibrated_derivatives_research_interest_not_profit_probability"
MODEL = "BSM_EUROPEAN_CASH_INDEX_ACT365F"
_REPORT_CONTEXT = Context(prec=512)


def _money(value: Decimal) -> str:
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _error(exc, *, code=None):
    return {"schema_version": 1, "success": False, "research_only": True,
            "model_status": "unvalidated_heuristic", "performance_validated": False,
            "code": code or getattr(exc, "code", "INVALID_DERIVATIVE_SNAPSHOT"),
            "error": str(exc), "data_mode": "unavailable",
            "metrics": {}, "blockers": [code or getattr(exc, "code", "INVALID_DERIVATIVE_SNAPSHOT")],
            "missing_data": [], "warnings": [], "recommendation": {
                "score": None, "score_type": SCORE_TYPE, "scope": "contract_specific",
                "verdict": "ABSTAIN", "strong_buy": False, "directional_support": None,
                "contract_quality": None, "horizon": "days_to_weeks_not_intraday_execution"}}


def _cutoff(as_of):
    from .derivative_contracts import aware_time
    return datetime.now(timezone.utc) if as_of is None else aware_time(as_of)


def _technical(snapshot):
    from .indicators import technical
    bars = snapshot["underlying"]["bars"]
    if not bars:
        return {}, []
    notes = []
    raw = technical(bars, "raw", notes)
    # Avoid exposing equity dollar-volume or stock accounting as index liquidity.
    keys = ("sma20", "sma50", "sma200", "ema12", "ema26", "macd", "rsi14", "atr14")
    return {"last_close": bars[-1]["close"], **{k: raw[k] for k in keys}}, notes


def _report(snapshot, cutoff):
    from .derivative_policy import POLICY_VERSION
    copied = deepcopy(snapshot)
    validation = copied.pop("_validation")
    source = copied["source"]
    source["data_mode"] = "fixture" if source["data_mode"] == "fixture" else "user_supplied"
    source["entitlement"] = "unverified"
    blockers = list(dict.fromkeys(validation["blockers"] + ["OFFLINE_PROVENANCE_UNVERIFIED"]))
    technical, warnings = _technical(copied)
    report = {"schema_version": 1, "success": True, "research_only": True,
              "model_status": "unvalidated_heuristic", "performance_validated": False,
              "policy_version": POLICY_VERSION, "data_mode": source["data_mode"],
              "provenance": {"ingress": "user_supplied_snapshot", "data_mode_is_caller_declared": True,
                             "independently_verified": False, "trusted_live_source": False},
              "contract": copied["contract"], "as_of": cutoff.isoformat(), "source": source,
              "source_clocks": {"quote_observed_at": copied["quote"]["observed_at"],
                                "quote_received_at": copied["quote"]["received_at"],
                                "underlying_spot_at": copied["underlying"]["spot_observed_at"],
                                "last_bar_finalized_at": copied["underlying"]["last_bar_finalized_at"]},
              "metrics": {"currency": copied["contract"]["currency"], "technical": technical},
              "missing_data": list(dict.fromkeys(validation["missing_data"])),
              "warnings": list(dict.fromkeys(validation["warnings"] + warnings + [
                  "Offline evidence is not a verified live feed. No orders or account-risk verification.",
                  "Direction and liquidity observations are not probabilities or performance validation."])),
              "blockers": blockers, "evidence_coverage": {}}
    usable = validation.get("usable", {})
    report["metrics"]["technical_observation_status"] = (
        "usable_for_direction" if usable.get("history") else "descriptive_only_unusable_history")
    present = {"underlying_history": bool(usable.get("history")),
               "quote_evidence": bool(usable.get("quote")),
               "cost_estimate": bool(usable.get("costs")),
               "rates": bool(usable.get("rates")),
               "margin_reference": bool(usable.get("margin")),
               "trusted_live_provenance": False}
    report["evidence_coverage"] = {"checks": present, "available": sum(present.values()),
                                    "total": len(present), "not_a_prediction_confidence": True}
    return report, copied, usable


def _recommendation(report, snapshot, *, side, scope):
    from .derivative_contracts import decimal_value
    from .derivative_policy import directional_support, research_interest
    metrics = report["metrics"]["technical"]
    direction = (directional_support(metrics, side)
                 if report["evidence_coverage"]["checks"]["underlying_history"] else None)
    bid, ask = (decimal_value(snapshot["quote"][k]) for k in ("bid", "ask"))
    spread = float((ask-bid)/((ask+bid)/2))
    view = research_interest(direction, spread, blockers=report["blockers"])
    return {**view, "score_type": SCORE_TYPE, "scope": scope,
            "directional_support": direction, "horizon": "days_to_weeks_not_intraday_execution",
            "reason_codes": list(report["blockers"])}


def _quote_metrics(snapshot):
    from .derivative_contracts import decimal_value
    q = snapshot["quote"]
    bid, ask = decimal_value(q["bid"]), decimal_value(q["ask"])
    return {"bid": _money(bid), "ask": _money(ask), "spread": _money(ask-bid),
            "spread_fraction": float((ask-bid)/((ask+bid)/2)),
            "reference_midpoint": _money((ask+bid)/2), "midpoint_is_execution": False,
            "bid_contracts": q["bid_contracts"], "ask_contracts": q["ask_contracts"],
            "market_state": q["market_state"], "delay_seconds": q["delay_seconds"]}


def _cost_value(snapshot, usable):
    from .derivative_contracts import decimal_value
    return decimal_value(snapshot["costs"]["round_trip_per_contract"]) if usable.get("costs") else None


def _future(report, snapshot, usable):
    from .derivative_contracts import decimal_value
    from .derivative_math import futures_pnl
    c, q = snapshot["contract"], snapshot["quote"]
    multiplier, tick = decimal_value(c["value_per_price_unit"]), decimal_value(c["tick_size"])
    bid, ask = decimal_value(q["bid"]), decimal_value(q["ask"])
    midpoint, costs = (bid+ask)/2, _cost_value(snapshot, usable)
    scenarios = []
    for move in (Decimal("-0.10"), Decimal("-0.05"), Decimal(0), Decimal("0.05"), Decimal("0.10")):
        price = midpoint*(1+move)
        long = futures_pnl(ask, price, multiplier, side="long")
        short = futures_pnl(bid, price, multiplier, side="short")
        scenarios.append({"future_price": _money(price), "fractional_move_from_reference": str(move),
                          "long_gross_pnl": _money(long), "short_gross_pnl": _money(short),
                          "long_net_pnl_after_supplied_costs": _money(long-costs) if costs is not None else None,
                          "short_net_pnl_after_supplied_costs": _money(short-costs) if costs is not None else None})
    report["strategy"] = "index_future_directional_research"
    report["metrics"]["quote"] = _quote_metrics(snapshot)
    report["metrics"]["futures"] = {
        "contracts": 1, "quantity_unit": "contracts", "value_per_price_unit": _money(multiplier),
        "tick_value": _money(tick*multiplier), "long_entry_ask": _money(ask), "short_entry_bid": _money(bid),
        "gross_notional_at_ask": _money(abs(ask*multiplier)), "gross_notional_at_bid": _money(abs(bid*multiplier)),
        "maximum_loss": None, "maximum_loss_status": "not_capped_by_margin_or_stop",
        "account_affordability": "unverified", "margin_reference": snapshot.get("margin") if usable.get("margin") else None,
        "cost_status": "supplied_estimate_unverified" if costs is not None else "unavailable",
        "scenario_anchor": "futures_midpoint_reference_not_fill_or_spot_forecast", "scenarios": scenarios}
    report["recommendations"] = {side: _recommendation(report, snapshot, side=side, scope=f"future_{side}")
                                  for side in ("long", "short")}
    report["recommendation"] = report["recommendations"]["long"]
    return report


def _option_pricing(snapshot, usable, cutoff):
    from .derivative_contracts import aware_time, decimal_value
    from .derivative_math import bsm_greeks, implied_volatility
    unavailable = {"model": MODEL, "status": "unavailable", "independent_valuation": False,
                   "iv_midpoint": None, "iv_bid": None, "iv_ask": None,
                   "greeks_per_premium_unit": None, "greeks_per_contract": None,
                   "midpoint_is_execution": False, "reason_codes": []}
    if not usable.get("rates"):
        unavailable["reason_codes"].append("DATED_MATCHING_RATES_UNAVAILABLE")
    if not usable.get("quote"):
        unavailable["reason_codes"].append("DATED_MATCHING_QUOTE_UNAVAILABLE")
    if unavailable["reason_codes"]:
        return unavailable
    c, q, u, rates = (snapshot[key] for key in ("contract", "quote", "underlying", "rates"))
    years = (aware_time(c["expiry_at"]) - cutoff).total_seconds() / (365 * 24 * 60 * 60)
    parameters = (u["spot"], c["strike"], years, rates["risk_free"], rates["dividend_yield"])
    midpoint = (decimal_value(q["bid"]) + decimal_value(q["ask"])) / 2
    try:
        middle_iv = implied_volatility(midpoint, *parameters, right=c["right"])
        bid_iv = implied_volatility(q["bid"], *parameters, right=c["right"])
        ask_iv = implied_volatility(q["ask"], *parameters, right=c["right"])
        greeks = bsm_greeks(*parameters, middle_iv, right=c["right"])
        scale = float(decimal_value(c["value_per_price_unit"]))
        scaled = {key: value * scale for key, value in greeks.items()}
        import math
        if not all(math.isfinite(value) for value in scaled.values()):
            raise ValueError("NONFINITE_CONTRACT_SENSITIVITY")
    except (ValueError, TypeError, ArithmeticError) as exc:
        unavailable["reason_codes"] = [str(exc)]
        return unavailable
    return {**unavailable, "status": "available", "iv_midpoint": middle_iv,
            "iv_bid": bid_iv, "iv_ask": ask_iv, "iv_units": "annualized_volatility_fraction",
            "greeks_per_premium_unit": greeks, "greeks_per_contract": scaled,
            "greek_basis": "delta_per_index_point; gamma_per_index_point_squared; vega/rho_per_percentage_point; theta_per_calendar_day",
            "years_act365f": years, "rate_evidence": deepcopy(rates),
            "volatility_source": "inverted_same_quote_not_independent_fair_value",
            "reason_codes": []}


def _option(report, snapshot, usable, cutoff):
    from .derivative_contracts import decimal_value
    from .derivative_math import long_option_pnl
    c, q, u = (snapshot[key] for key in ("contract", "quote", "underlying"))
    spot, strike, ask, multiplier = (decimal_value(value) for value in (
        u["spot"], c["strike"], q["ask"], c["value_per_price_unit"]))
    right = c["right"]
    intrinsic = max(spot-strike if right == "call" else strike-spot, Decimal(0))
    costs = _cost_value(snapshot, usable)
    pricing = _option_pricing(snapshot, usable, cutoff)
    if pricing["status"] != "available":
        report["blockers"].append("OPTION_PRICING_UNAVAILABLE")
        report["warnings"].extend(pricing["reason_codes"])
    premium = ask*multiplier
    breakeven = strike+ask if right == "call" else strike-ask
    scenarios = []
    for factor in (Decimal("0.8"), Decimal("0.9"), Decimal(1), Decimal("1.1"), Decimal("1.2")):
        terminal = spot*factor
        gross = long_option_pnl(terminal, strike, ask, multiplier, right=right)
        scenarios.append({"terminal_underlying": _money(terminal), "gross_pnl": _money(gross),
                          "net_pnl_after_supplied_costs": _money(gross-costs) if costs is not None else None})
    report["strategy"] = "long_"+right
    report["metrics"]["quote"] = _quote_metrics(snapshot)
    report["metrics"]["option"] = {
        "contracts": 1, "quantity_unit": "contracts", "entry_premium_ask": _money(ask),
        "gross_premium_outlay": _money(premium), "intrinsic_at_spot": _money(intrinsic),
        "time_value_at_ask": _money(ask-intrinsic),
        "gross_max_loss": _money(premium),
        "estimated_max_loss_including_supplied_costs": _money(premium+costs) if costs is not None else None,
        "maximum_expiry_pnl_gross": None if right == "call" else _money((strike-ask)*multiplier),
        "max_profit_status": "unbounded" if right == "call" else "bounded",
        "breakeven_gross": _money(breakeven), "breakeven_attainable": breakeven >= 0,
        "cost_status": "supplied_estimate_unverified" if costs is not None else "unavailable",
        "excluded_costs": snapshot["costs"]["excludes"] if costs is not None else None,
        "expiry_bounds_are_before_unknown_costs": True,
        "scenario_type": "hypothetical_expiry_underlying_not_forecast", "scenarios": scenarios,
        "pricing": pricing}
    report["recommendation"] = _recommendation(report, snapshot,
                                              side="long" if right == "call" else "short", scope="long_"+right)
    return report


def analyze_derivative_snapshot(snapshot, *, as_of=None):
    """Analyze an explicit offline snapshot; no I/O or trusted-source override."""
    from .derivative_contracts import validate_snapshot
    try:
        cutoff = _cutoff(as_of)
        normalized = validate_snapshot(snapshot, as_of=cutoff.isoformat())
        with localcontext(_REPORT_CONTEXT):
            report, normalized, usable = _report(normalized, cutoff)
            if normalized["contract"]["family"] == "index_future":
                return _future(report, normalized, usable)
            return _option(report, normalized, usable, cutoff)
    except (ValueError, TypeError, KeyError, ArithmeticError, AttributeError, RecursionError) as exc:
        return _error(exc)


def analyze_debit_vertical(long_snapshot, short_snapshot, *, as_of=None):
    """One-to-one matched European cash-index debit spread, never an order."""
    from .derivative_contracts import aware_time, decimal_value, validate_snapshot
    from .derivative_math import debit_vertical, long_option_pnl
    from .derivative_policy import directional_support, research_interest
    try:
        cutoff = _cutoff(as_of)
        long = validate_snapshot(long_snapshot, as_of=cutoff.isoformat())
        short = validate_snapshot(short_snapshot, as_of=cutoff.isoformat())
        lc, sc = long["contract"], short["contract"]
        if lc["family"] != "index_option" or sc["family"] != "index_option":
            return _error("both spread legs must be European cash-index options", code="UNSUPPORTED_STRATEGY")
        matched = ("venue", "root", "underlying_id", "currency", "right", "exercise",
                   "settlement", "standard_deliverable", "underlying_kind")
        if any(lc[key] != sc[key] for key in matched):
            return _error("spread contract identities/styles must match", code="MISMATCHED_SPREAD_LEGS")
        if (lc["contract_id"] == sc["contract_id"]
                or any(aware_time(lc[key]) != aware_time(sc[key]) for key in ("expiry_at", "last_trade_at"))
                or decimal_value(lc["value_per_price_unit"]) != decimal_value(sc["value_per_price_unit"])):
            return _error("spread requires distinct IDs, same expiry and multiplier", code="MISMATCHED_SPREAD_LEGS")
        if decimal_value(long["underlying"]["spot"]) != decimal_value(short["underlying"]["spot"]):
            return _error("spread requires a coherent common underlying spot", code="MISMATCHED_SPREAD_EVIDENCE")
        # One directional series must describe both legs. Equal current spot/ID
        # alone cannot reconcile conflicting histories or source attestations.
        history_fields = ("underlying_id", "currency", "interval", "price_basis", "adjustment", "source", "bars")
        if (any(long["underlying"][field] != short["underlying"][field] for field in history_fields)
                or aware_time(long["underlying"]["last_bar_finalized_at"])
                != aware_time(short["underlying"]["last_bar_finalized_at"])):
            return _error("spread requires matching underlying history, basis and finalization evidence",
                          code="MISMATCHED_SPREAD_EVIDENCE")
        with localcontext(_REPORT_CONTEXT):
            lr, long, lu = _report(long, cutoff)
            sr, short, su = _report(short, cutoff)
            lr = _option(lr, long, lu, cutoff)
            sr = _option(sr, short, su, cutoff)
            right, multiplier = lc["right"], decimal_value(lc["value_per_price_unit"])
            ask, bid = decimal_value(long["quote"]["ask"]), decimal_value(short["quote"]["bid"])
            bounds = debit_vertical(lc["strike"], sc["strike"], ask, bid, multiplier, right=right)
            blockers = list(dict.fromkeys(lr["blockers"] + sr["blockers"]))
            for key in ("observed_at", "received_at"):
                if abs((aware_time(long["quote"][key])-aware_time(short["quote"][key])).total_seconds()) > 5:
                    blockers.append("LEG_QUOTE_SKEW")
            if abs((aware_time(long["underlying"]["spot_observed_at"])-aware_time(short["underlying"]["spot_observed_at"])).total_seconds()) > 5:
                blockers.append("LEG_UNDERLYING_CLOCK_SKEW")
            costs_l, costs_s = _cost_value(long, lu), _cost_value(short, su)
            costs = costs_l+costs_s if costs_l is not None and costs_s is not None else None
            spot = decimal_value(long["underlying"]["spot"])
            scenarios = []
            for factor in (Decimal("0.8"), Decimal("0.9"), Decimal(1), Decimal("1.1"), Decimal("1.2")):
                terminal = spot*factor
                gross = (long_option_pnl(terminal, lc["strike"], ask, multiplier, right=right)
                         - long_option_pnl(terminal, sc["strike"], bid, multiplier, right=right))
                scenarios.append({"terminal_underlying": _money(terminal), "gross_pnl": _money(gross),
                                  "net_pnl_after_supplied_costs": _money(gross-costs) if costs is not None else None})
            spread_cost = ((decimal_value(long["quote"]["ask"])-decimal_value(long["quote"]["bid"]))
                           + (decimal_value(short["quote"]["ask"])-decimal_value(short["quote"]["bid"]))) * multiplier
            liquidation = (decimal_value(long["quote"]["bid"])-decimal_value(short["quote"]["ask"]))*multiplier
            strategy = "bull_call_debit" if right == "call" else "bear_put_debit"
            # A single declared fixture does not make an otherwise imported
            # spread wholly synthetic. Preserve each leg's declared mode.
            mode = "fixture" if lr["data_mode"] == sr["data_mode"] == "fixture" else "user_supplied"
            direction = (directional_support(lr["metrics"]["technical"], "long" if right == "call" else "short")
                         if lu.get("history") and su.get("history") else None)
            interest = research_interest(direction, float(spread_cost/bounds["debit"]), blockers=blockers)
            report = {**lr, "strategy": strategy, "blockers": list(dict.fromkeys(blockers)),
                      "atomic_fill_guaranteed": False,
                      "data_mode": mode,
                      "provenance": {**lr["provenance"],
                                     "mixed_declared_modes": lr["data_mode"] != sr["data_mode"],
                                     "legs": {"long": lr["provenance"], "short": sr["provenance"]}},
                      "contract": {key: value for key, value in lc.items() if key not in ("contract_id", "strike")},
                      "source": {"data_mode": mode,
                                 "entitlement": "unverified", "legs": {"long": lr["source"], "short": sr["source"]}},
                      "source_clocks": {"long": lr["source_clocks"], "short": sr["source_clocks"]},
                      "legs": [{"role": role, "contract_id": item["contract"]["contract_id"],
                                "contract": item["contract"], "source": item["source"],
                                "pricing": item["metrics"]["option"]["pricing"]}
                               for role, item in (("long", lr), ("short", sr))],
                      "metrics": {"currency": lc["currency"], "technical": lr["metrics"]["technical"],
                                  "vertical": {"contracts_each_leg": 1, "quantity_unit": "contracts",
                                               "gross_debit": _money(bounds["debit"]),
                                               "gross_max_loss": _money(bounds["max_loss_gross"]),
                                               "gross_max_profit": _money(bounds["max_profit_gross"]),
                                               "breakeven_gross": _money(bounds["breakeven"]),
                                               "estimated_max_loss_including_supplied_costs": _money(bounds["debit"]+costs) if costs is not None else None,
                                               "estimated_leg_spread_cost": _money(spread_cost),
                                               "net_liquidation_at_supplied_leg_books": _money(liquidation),
                                               "cost_status": "supplied_estimate_unverified" if costs is not None else "unavailable",
                                               "expiry_bounds_are_before_unknown_costs": True,
                                               "scenarios": scenarios}},
                      "missing_data": list(dict.fromkeys(lr["missing_data"]+sr["missing_data"])),
                      "warnings": list(dict.fromkeys(lr["warnings"]+sr["warnings"]+[
                          "Two leg estimates are not an atomic executable spread quote; expiry bounds exclude legging and omitted costs."])),
                      "evidence_coverage": {"legs": {"long": lr["evidence_coverage"], "short": sr["evidence_coverage"]},
                                            "not_a_prediction_confidence": True},
                      "recommendation": {**interest, "score_type": SCORE_TYPE, "scope": strategy,
                                         "directional_support": direction, "horizon": "days_to_weeks_not_intraday_execution",
                                         "reason_codes": list(dict.fromkeys(blockers))}}
            return report
    except (ValueError, TypeError, KeyError, ArithmeticError, AttributeError, RecursionError) as exc:
        return _error(exc)


def analyze_derivative_request(snapshot, *, short_leg=None, as_of=None):
    """Shared CLI/native dispatcher; an optional leg is never a naked short."""
    if short_leg is None:
        return analyze_derivative_snapshot(snapshot, as_of=as_of)
    if not isinstance(short_leg, dict):
        return _error("short_leg must be a normalized option snapshot")
    return analyze_debit_vertical(snapshot, short_leg, as_of=as_of)


def recommend_derivatives(requests, *, kind, provider, supplemental_by_root=None, as_of=None):
    """Orchestrate caller-injected offline data; no built-in live feed is added.

    The provider is a Python data interface, never a model-supplied URL or
    credential argument. This library-only path preserves unverified provenance
    and abstention. CLI/native root requests remain unavailable in M1.
    """
    from .derivative_batches import recommend_derivatives as execute
    return execute(requests, kind=kind, provider=provider,
                   supplemental_by_root=supplemental_by_root, as_of=as_of)


def derivative_roots_unavailable(requests, *, kind="options", as_of=None):
    """Validate a root request and truthfully decline unimplemented live access.

    This unavailable CLI path constructs no provider, reads no credentials and
    makes no market request. A separate library API can orchestrate explicitly
    injected offline data; it does not enable root-only live access here.
    """
    from .derivative_contracts import parse_root_requests
    try:
        parsed = parse_root_requests(requests)
        if not isinstance(kind, str) or kind not in ("futures", "options"):
            raise ValueError("kind must be futures or options")
        cutoff = _cutoff(as_of)
        result = _error("M1 is offline only. Supply --snapshot; derivative root feeds require separately authorized M2 integration.",
                        code="DERIVATIVES_PROVIDER_NOT_IMPLEMENTED")
        result.update({**parsed, "kind": kind, "as_of": cutoff.isoformat(),
                       "requested_count": len(parsed["requested"]), "unique_count": len(parsed["roots"]),
                       "analyzed_count": 0, "eligible_count": 0, "abstained_count": 0,
                       "failed_count": len(parsed["roots"]), "provider_attempted": False})
        return result
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        return _error(exc, code="INVALID_DERIVATIVE_ARGUMENTS")
