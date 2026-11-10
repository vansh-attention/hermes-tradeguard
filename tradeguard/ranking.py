"""Research prioritization within an explicit comparable snapshot universe."""
from __future__ import annotations


def rank_snapshots(snapshots: list[dict], as_of: str | None = None) -> dict:
    if not isinstance(snapshots, list) or not 1 <= len(snapshots) <= 50:
        raise ValueError("provide 1..50 explicit snapshots")
    if not all(isinstance(s, dict) for s in snapshots):
        raise ValueError("snapshots must be objects")
    symbols = [s.get("symbol") for s in snapshots]
    if not all(isinstance(s, str) and s for s in symbols) or len(symbols) != len(set(symbols)):
        raise ValueError("universe symbols must be unique nonempty strings")
    if len({s.get("asset_type") for s in snapshots}) != 1:
        raise ValueError("rank within one instrument family; stock and ETF scoring scales differ")
    if len({s.get("currency") for s in snapshots}) != 1:
        raise ValueError("rank within one currency; no implicit FX conversion")
    effective_dates = []
    for s in snapshots:
        bars = s.get("bars", [])
        usable = [b.get("date") for b in bars if isinstance(b, dict) and isinstance(b.get("date"), str) and (as_of is None or b["date"] <= as_of)]
        effective_dates.append(usable[-1] if usable else None)
    if len(set(effective_dates)) != 1:
        raise ValueError("ranked snapshots must have the same effective last-bar date")
    from .equity import analyze_snapshot
    reports = [analyze_snapshot(s, as_of=as_of) for s in snapshots]
    eligible, abstained = [], []
    for report in reports:
        rec = report.get("recommendation", {})
        (abstained if rec.get("action") == "ABSTAIN" or rec.get("score") is None else eligible).append(report)
    eligible.sort(key=lambda r: (-(r["recommendation"]["score"] or 0), r.get("symbol", "")))
    for i, report in enumerate(eligible, 1):
        report["research_rank"] = i
    return {"ranked": eligible, "abstained": abstained, "universe_size": len(snapshots), "universe": symbols,
            "asset_type": snapshots[0].get("asset_type"), "currency": snapshots[0].get("currency"),
            "last_bar_date": effective_dates[0], "research_only": True, "model_status": "unvalidated_heuristic",
            "warning": "Research priorities, NOT win probabilities or trade allocations. User-selected universe may have survivorship/selection bias; no all-market coverage implied."}
