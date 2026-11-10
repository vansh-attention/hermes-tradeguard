"""Small offline derivative text view. No provider, prompts or side effects on load."""
from __future__ import annotations

import math

# Share the existing terminal-control sanitizer; keep provider text as data.
from .ticker_ui import _line


def _score(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        return "N/A"
    return f"{value:.2f}"


def render_derivative_results(result: dict) -> str:
    lines = ["TradeGuard — OFFLINE derivative research"]
    if not result.get("success"):
        lines.append(_line(result.get("code", "INVALID_DERIVATIVE_SNAPSHOT")) + ": " + _line(result.get("error", "Unavailable")))
        lines.append("No live feed or order placement is available in M1.")
        return "\n".join(lines)
    mode = result.get("data_mode")
    lines.append("SYNTHETIC / NOT LIVE" if mode == "fixture" else "USER-SUPPLIED / UNVERIFIED / NOT LIVE")
    contract = result.get("contract", {})
    currency = _line(contract.get("currency", "unknown"))
    lines.extend(["Contract: " + _line(contract.get("contract_id", "matched two-leg spread")),
                  "Strategy: " + _line(result.get("strategy", "unavailable")),
                  "Cutoff: " + _line(result.get("as_of", "unknown")),
                  "Expiry: " + _line(contract.get("expiry_at", "see legs"))])
    views = result.get("recommendations") or {"selected": result["recommendation"]}
    lines.append("Scope                 Interest    Directional support    Verdict")
    for view in views.values():
        scope = _line(view.get("scope", "contract_specific"))
        lines.append(f"{scope:<21} {_score(view.get('score')):<11} {_score(view.get('directional_support')):<22} {_line(view.get('verdict', 'ABSTAIN'))}")
    metrics = result.get("metrics", {})
    if "futures" in metrics:
        future = metrics["futures"]
        lines.append("Gross notional at ask: " + _line(future.get("gross_notional_at_ask", "N/A")) + " " + currency)
        lines.append("Maximum loss: not capped by margin or a stop. Account affordability: UNVERIFIED.")
    if "option" in metrics:
        option = metrics["option"]
        lines.append("Gross expiry max loss: " + _line(option.get("gross_max_loss", "N/A")) + " " + currency)
        pricing = option.get("pricing", {})
        lines.append("European model/Greeks: " + _line(pricing.get("status", "unavailable")) + "; not independent fair-value evidence.")
    if "vertical" in metrics:
        vertical = metrics["vertical"]
        lines.append("Gross expiry max loss: " + _line(vertical.get("gross_max_loss", "N/A")) + " " + currency)
        lines.append("Gross expiry max profit: " + _line(vertical.get("gross_max_profit", "N/A")) + " " + currency)
        lines.append("Leg estimates are not an atomic executable spread quote.")
        for leg in result.get("legs", []):
            lines.append("  Leg: " + _line(leg.get("contract_id", "unknown")))
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
