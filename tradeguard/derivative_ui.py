"""Small offline derivative text view. No provider, prompts or side effects on load."""
from __future__ import annotations

import json
import math
import sys


def _line(value):
    """Keep provider text on one inert terminal line, including Unicode controls."""
    if value is None:
        return "N/A"
    text = "".join(char if char.isprintable() else " " for char in str(value))
    return text.strip() or "N/A"


def _score(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        return "N/A"
    return f"{value:.2f}"


def _clock_lines(clocks, *, prefix=""):
    clocks = clocks or {}
    return [prefix + label + ": " + _line(clocks.get(key))
            for label, key in (("Quote observed at", "quote_observed_at"),
                               ("Quote received at", "quote_received_at"),
                               ("Underlying spot at", "underlying_spot_at"))]


def render_derivative_results(result: dict) -> str:
    lines = ["TradeGuard — OFFLINE derivative research"]
    if not result.get("success"):
        lines.append(_line(result.get("code", "INVALID_DERIVATIVE_SNAPSHOT")) + ": " + _line(result.get("error", "Unavailable")))
        lines.append("No live feed or order placement is available in M1.")
        return "\n".join(lines)
    mode = result.get("data_mode")
    lines.append("CALLER-DECLARED SYNTHETIC / UNVERIFIED / NOT LIVE" if mode == "fixture" else "USER-SUPPLIED / UNVERIFIED / NOT LIVE")
    contract = result.get("contract", {})
    currency = _line(contract.get("currency", "N/A"))
    lines.extend(["Contract: " + _line(contract.get("contract_id", "matched two-leg spread" if result.get("legs") else "N/A")),
                  "Strategy: " + _line(result.get("strategy", "N/A")),
                  "Cutoff: " + _line(result.get("as_of", "N/A")),
                  "Expiry: " + _line(contract.get("expiry_at", "N/A"))])
    views = result.get("recommendations") or {"selected": result["recommendation"]}
    lines.append("Scope                 Interest    Directional support    Verdict")
    for view in views.values():
        scope = _line(view.get("scope", "contract_specific"))
        lines.append(f"{scope:<21} {_score(view.get('score')):<11} {_score(view.get('directional_support')):<22} {_line(view.get('verdict', 'ABSTAIN'))}")
    metrics = result.get("metrics", {})
    if "futures" in metrics or "option" in metrics:
        lines.extend(_clock_lines(result.get("source_clocks")))
    if "futures" in metrics:
        future = metrics["futures"]
        lines.extend([
            "Multiplier: " + _line(contract.get("value_per_price_unit", "N/A")) + " " + currency + " per index point per contract",
            "Tick size: " + _line(contract.get("tick_size", "N/A")) + " index points",
            "Quantity: " + _line(future.get("contracts", "N/A")) + " contracts",
            "Long entry (ask): " + _line(future.get("long_entry_ask", "N/A")) + " index points",
            "Short entry (bid): " + _line(future.get("short_entry_bid", "N/A")) + " index points",
            "Tick value: " + _line(future.get("tick_value", "N/A")) + " " + currency + " per tick per contract",
            "Gross notional at ask: " + _line(future.get("gross_notional_at_ask", "N/A")) + " " + currency,
            "Gross notional at bid: " + _line(future.get("gross_notional_at_bid", "N/A")) + " " + currency,
        ])
        lines.append("Maximum loss: not capped by margin or a stop. Account affordability: UNVERIFIED.")
    if "option" in metrics:
        option = metrics["option"]
        lines.extend([
            "Right: " + _line(contract.get("right", "N/A")),
            "Strike: " + _line(contract.get("strike", "N/A")) + " index points",
            "Multiplier: " + _line(contract.get("value_per_price_unit", "N/A")) + " " + currency + " per index point per contract",
            "Quantity: " + _line(option.get("contracts", "N/A")) + " contracts",
            "Entry premium (ask): " + _line(option.get("entry_premium_ask", "N/A")) + " index points",
            "Gross premium outlay: " + _line(option.get("gross_premium_outlay", "N/A")) + " " + currency,
            "Gross expiry breakeven: " + _line(option.get("breakeven_gross", "N/A")) + " underlying index points",
            "Gross expiry max loss: " + _line(option.get("gross_max_loss", "N/A")) + " " + currency,
        ])
        pricing = option.get("pricing") or {}
        lines.append("European model/Greeks: " + _line(pricing.get("status", "N/A")) + "; not independent fair-value evidence.")
    if "vertical" in metrics:
        vertical = metrics["vertical"]
        lines.extend([
            "Quantity per leg: " + _line(vertical.get("contracts_each_leg", "N/A")) + " contracts",
            "Gross debit: " + _line(vertical.get("gross_debit", "N/A")) + " " + currency,
            "Gross expiry breakeven: " + _line(vertical.get("breakeven_gross", "N/A")) + " underlying index points",
            "Gross expiry max loss: " + _line(vertical.get("gross_max_loss", "N/A")) + " " + currency,
            "Gross expiry max profit: " + _line(vertical.get("gross_max_profit", "N/A")) + " " + currency,
        ])
        lines.append("Leg estimates are not an atomic executable spread quote.")
        for leg in result.get("legs", []):
            role = leg.get("role")
            leg_contract = leg.get("contract", {})
            leg_currency = _line(leg_contract.get("currency", "N/A"))
            lines.extend([
                "  Leg (" + _line(role) + "): " + _line(leg.get("contract_id", "N/A")),
                "    Right: " + _line(leg_contract.get("right", "N/A")),
                "    Strike: " + _line(leg_contract.get("strike", "N/A")) + " index points",
                "    Multiplier: " + _line(leg_contract.get("value_per_price_unit", "N/A")) + " " + leg_currency + " per index point per contract",
                "    Expiry: " + _line(leg_contract.get("expiry_at", "N/A")),
            ])
            lines.extend(_clock_lines((result.get("source_clocks") or {}).get(role), prefix="    "))
    for label, key in (("Blocker", "blockers"), ("Missing", "missing_data"), ("Warning", "warnings")):
        values = result.get(key, [])
        for value in values[:3]:
            lines.append(f"{label}: " + _line(value))
        if len(values) > 3:
            lines.append(f"{label}: {len(values)-3} more; see JSON for the complete list.")
    lines.extend(["", "N/A means abstain/unavailable, not zero interest.",
                  "Interest and directional support are heuristics, NOT probabilities of profit.",
                  "Expiry payoffs are gross scenarios, not price forecasts or guaranteed exits.",
                  "No live feeds, account access or order placement in M1."])
    return "\n".join(lines)


def run_derivative_prompt(*, kind="options", as_of=None, json_output=False) -> int:
    """Explicit CLI-only root prompt; never fetch or read credentials in M1."""
    from .derivatives import derivative_roots_unavailable
    print("TradeGuard derivatives M1: OFFLINE / NOT LIVE. Enter VENUE:ROOT; live feeds are unavailable. Type quit to exit.", file=sys.stderr)
    while True:
        print("Derivatives> ", file=sys.stderr, end="", flush=True)
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            print("\nStopped.", file=sys.stderr)
            return 130
        if line == "":
            return 0
        text = line.strip()
        if not text:
            continue
        if text.lower() in ("quit", "exit", ":q", ":quit"):
            return 0
        result = derivative_roots_unavailable(text, kind=kind, as_of=as_of)
        print(json.dumps(result, allow_nan=False) if json_output else render_derivative_results(result))
