"""Bounded offline batches using only a caller-injected Python provider.

No provider registry, credentials, network adapter, or executable recommendation.
Provider evidence is always unverified user-supplied data, never a live feed.
"""

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, localcontext

from .derivative_contracts import (
    DerivativeInputError, _bounded_json, _validate_history, aware_time, decimal_value,
    parse_root_requests, select_contracts,
)
from .derivatives import _error, analyze_derivative_snapshot


__all__ = ["recommend_derivatives"]


def _source(received_at):
    return {
        "provider": "injected_offline_provider", "retrieved_at": received_at,
        "data_mode": "user_supplied", "entitlement": "unverified",
        "historical_vintage": "Caller-injected offline history; vintage unverified",
    }


def _failure(exc, code="DERIVATIVES_PROVIDER_ERROR"):
    return {**_error(exc, code=getattr(exc, "code", code)),
            "source": _source(None), "data_mode": "user_supplied"}


def _history_snapshot(underlying):
    try:
        _bounded_json(underlying)
        required = {"underlying_id", "currency", "spot", "spot_observed_at", "interval", "price_basis",
                    "adjustment", "source", "retrieved_at", "bars", "last_bar_finalized_at"}
        if type(underlying) is not dict or set(underlying) != required:
            raise ValueError("missing or unknown canonical underlying fields")
        # Check internal history consistency before replacing any refresh fields.
        # Freshness relative to the final cutoff is rechecked by the analyzer.
        validation = {"blockers": [], "missing_data": [], "usable": {}}
        _validate_history(underlying, aware_time(underlying["retrieved_at"]), validation)
        aware_time(underlying["spot_observed_at"])
        return deepcopy(underlying)
    except (ValueError, TypeError, KeyError, ArithmeticError, RecursionError) as exc:
        raise DerivativeInputError("INVALID_DERIVATIVE_PROVIDER_HISTORY", str(exc)) from exc


def _validate_packet(packet, pending):
    identifiers = {contract["contract_id"] for _, contract, _ in pending}
    roots = {row["root"] for row, _, _ in pending}
    try:
        if type(packet) is not dict or set(packet) != {"quotes", "underlyings", "received_at"}:
            raise ValueError("quote packet requires exactly quotes, underlyings, received_at")
        for name, allowed, limit in (("quotes", identifiers, 24), ("underlyings", roots, 3)):
            values = packet[name]
            if type(values) is not dict or len(values) > limit or not values.keys() <= allowed:
                raise ValueError(f"{name} requires bounded exact selected identity keys")
        aware_time(packet["received_at"])
    except (ValueError, TypeError, KeyError) as exc:
        raise DerivativeInputError("INVALID_DERIVATIVE_PROVIDER_PACKET", str(exc)) from exc


def _supplemental_fields(entry, selected, contract):
    try:
        if type(entry) is not dict or entry.keys() - {"rates", "margin_by_contract", "costs_by_contract"}:
            raise ValueError("supplemental root entry requires only rates, margin_by_contract, costs_by_contract")
        identifiers = {item["contract_id"] for item in selected}
        evidence = {"rates": entry["rates"]} if "rates" in entry else {}
        for name in ("margin", "costs"):
            values = entry.get(name + "_by_contract", {})
            if type(values) is not dict or len(values) > 8 or not values.keys() <= identifiers:
                raise ValueError(f"{name}_by_contract requires exact selected full contract IDs")
            if contract["contract_id"] in values:
                evidence[name] = values[contract["contract_id"]]
        return evidence
    except (ValueError, TypeError, KeyError) as exc:
        raise DerivativeInputError("INVALID_DERIVATIVE_SUPPLEMENTAL", str(exc)) from exc


def _selected_report(row, contract, history, packet, cutoff, kind, supplemental_entry):
    try:
        evidence = _supplemental_fields(supplemental_entry, row["selection"]["selected"], contract)
        refresh = packet["underlyings"][row["root"]]
        fields = {"underlying_id", "currency", "spot", "spot_observed_at", "retrieved_at"}
        if type(refresh) is not dict or set(refresh) != fields:
            raise ValueError("missing or unknown refreshed underlying fields; old spot is not a fallback")
        for field in ("underlying_id", "currency"):
            if refresh[field] != contract[field] or history[field] != contract[field]:
                raise ValueError("history/refreshed underlying identity or currency mismatch")
        if aware_time(history["retrieved_at"]) > min(aware_time(cutoff), aware_time(packet["received_at"])):
            raise ValueError("original history retrieval is after final cutoff or final quote receipt")
        underlying = deepcopy(history)
        underlying.update(refresh)
        outside = False
        if kind == "options":
            with localcontext() as context:
                context.prec = 256
                spot, strike = decimal_value(underlying["spot"]), decimal_value(contract["strike"])
                outside = not spot * Decimal("0.95") <= strike <= spot * Decimal("1.05")
        if outside:
            code = "FINAL_STRIKE_OUTSIDE_SPOT_BAND"
            report = _failure("Selected strike outside refreshed spot band; no reselection", code)
            exclusions = row["selection"]["final_exclusion_reasons"]
            exclusions[code] = exclusions.get(code, 0) + 1
        else:
            report = analyze_derivative_snapshot({
                "schema_version": 1, "contract": contract,
                "quote": packet["quotes"][contract["contract_id"]], "underlying": underlying,
                "source": _source(packet["received_at"]), **evidence,
            }, as_of=cutoff)
    except (ValueError, TypeError, KeyError, ArithmeticError, AttributeError, RecursionError) as exc:
        report = _failure(exc, "INVALID_DERIVATIVE_PROVIDER_PACKET")
    report["contract_id"] = contract["contract_id"]
    report.setdefault("contract", deepcopy(contract))
    report.setdefault("source", _source(packet["received_at"]))
    report["data_mode"] = "user_supplied"
    return report


def _comparisons(row):
    groups = {}
    for report in row["reports"]:
        if not report["success"]:
            continue
        contract = report["contract"]
        key = (row["root"], contract["currency"], contract["family"], contract.get("right"))
        group = groups.setdefault(key, {
            "root": key[0], "currency": key[1], "family": key[2], "right": key[3],
            "ranking_status": "unavailable_offline_scores", "rows": [],
        })
        group["rows"].append({"contract_id": contract["contract_id"], "score": None, "rank": None})
    return list(groups.values())


def _summarize(parsed, kind, results, cutoff, received_at=None):
    reports = [report for row in results for report in row["reports"]]
    successful = [report for report in reports if report["success"]]
    analyzed = sum(row["success"] for row in results)
    return {
        "schema_version": 1, "success": bool(analyzed),
        "status": "analyzed" if all(row["status"] == "analyzed" for row in results) else "partial" if analyzed else "failed",
        "research_only": True, "model_status": "unvalidated_heuristic",
        "performance_validated": False, "kind": kind, "as_of": cutoff,
        "source": _source(received_at), "data_mode": "user_supplied", "provider_attempted": True,
        **parsed, "results": results, "requested_count": len(parsed["requested"]),
        "unique_count": len(results), "analyzed_count": analyzed,
        "failed_count": len(results) - analyzed, "eligible_count": 0, "abstained_count": analyzed,
        "contract_counts": {"total": len(reports), "successful": len(successful),
                            "failed": len(reports) - len(successful), "eligible": 0,
                            "abstained": len(successful)},
    }


def recommend_derivatives(requests, *, kind, provider, supplemental_by_root=None, as_of=None):
    """Return bounded, unverified research reports for 1..3 requested root tokens.

    ``kind`` is ``futures`` or ``options``. An injected Python object must expose:

    * ``instrument_records(roots)``: materialized list of <=1000 canonical contracts.
    * ``underlying_snapshot(root, as_of)``: canonical full daily-history object.
    * ``quotes(contract_ids, as_of)``: exactly ``quotes``, ``underlyings`` and an
      aware ``received_at``. Quote keys are exact full selected contract IDs;
      refresh keys are exact normalized VENUE:ROOT tokens. Each refresh contains
      underlying_id, currency, spot, spot_observed_at and retrieved_at only.

    Metadata is fetched once, histories in root order, then <=3 futures or <=24
    options in one final quote/spot call. Missing refreshes never reuse old spots;
    an updated spot may invalidate a selected strike but never trigger reselection.
    With no explicit aware ISO ``as_of``, the final cutoff is captured after fetch.

    ``supplemental_by_root`` accepts <=3 exact requested normalized root keys.
    Each entry permits rates (bound to the exact underlying) and margin_by_contract
    / costs_by_contract maps keyed by selected full IDs. Evidence objects retain
    the explicit identity, currency and dated fields required by validate_snapshot.
    Omitted evidence stays absent; malformed/stale evidence has no fallback.

    ``results`` preserves unique root order and contains selection, reports
    (including selected-contract error rows), status and scoped comparisons.
    Top-level counts use roots; contract_counts uses total/successful/failed/
    eligible/abstained reports. All final scores remain null in offline M1.
    Invalid arguments return INVALID_DERIVATIVE_ARGUMENTS without provider calls.
    No provider is registered, discovered, certified, or promoted to a live feed.
    """
    try:
        parsed = parse_root_requests(requests)
        if kind not in ("futures", "options"):
            raise ValueError("kind must be futures or options")
        cutoff = (datetime.now(timezone.utc) if as_of is None else aware_time(as_of)).isoformat()
        if any(not callable(getattr(provider, name, None)) for name in (
            "instrument_records", "underlying_snapshot", "quotes",
        )):
            raise ValueError("provider must implement the three offline provider methods")
        if supplemental_by_root is not None and (
            type(supplemental_by_root) is not dict or len(supplemental_by_root) > 3
            or not supplemental_by_root.keys() <= set(parsed["roots"])
        ):
            raise ValueError("supplemental_by_root requires <=3 exact requested root keys")
    except (ValueError, TypeError, AttributeError) as exc:
        return {**_error(exc, code="INVALID_DERIVATIVE_ARGUMENTS"), "provider_attempted": False,
                "source": _source(None), "data_mode": "user_supplied"}
    results = [{"root": root, "success": False, "status": "failed", "selection": None,
                "reports": [], "comparisons": []} for root in parsed["roots"]]
    pending = []
    try:
        records = provider.instrument_records(list(parsed["roots"]))
        if type(records) is not list or len(records) > 1000:
            raise DerivativeInputError("INVALID_DERIVATIVE_PROVIDER_METADATA", "metadata must be a list of <=1000 contracts")
    except Exception as exc:
        for row in results:
            row.update(_failure(exc))
        if as_of is None:
            cutoff = datetime.now(timezone.utc).isoformat()
        return _summarize(parsed, kind, results, cutoff)
    for row in results:
        root = row["root"]
        try:
            underlying = _history_snapshot(provider.underlying_snapshot(root, as_of))
            row["selection"] = select_contracts(records, root, kind=kind, as_of=cutoff, spot=underlying["spot"])
            row["selection"]["final_exclusion_reasons"] = {}
            if not row["selection"]["selected"]:
                row.update(_failure("No contract satisfies the bounded metadata selection policy",
                                    "NO_ELIGIBLE_DERIVATIVE_CONTRACTS"))
            for contract in row["selection"]["selected"]:
                pending.append((row, contract, underlying))
        except Exception as exc:
            row.update(_failure(exc))
    packet = None
    if pending:
        try:
            packet = provider.quotes([contract["contract_id"] for _, contract, _ in pending], as_of)
            _validate_packet(packet, pending)
        except Exception as exc:
            for row, contract, _ in pending:
                row["reports"].append({**_failure(exc), "contract_id": contract["contract_id"]})
            pending = []
            packet = None
    if as_of is None:
        cutoff = datetime.now(timezone.utc).isoformat()
    for row, contract, history in pending:
        supplemental_entry = {} if supplemental_by_root is None else supplemental_by_root.get(row["root"], {})
        row["reports"].append(_selected_report(row, contract, history, packet, cutoff, kind, supplemental_entry))
    for row in results:
        row["success"] = any(report["success"] for report in row["reports"])
        failed = any(not report["success"] for report in row["reports"])
        row["status"] = "partial" if row["success"] and failed else "analyzed" if row["success"] else "failed"
        row["comparisons"] = _comparisons(row)
    return _summarize(parsed, kind, results, cutoff, None if packet is None else packet["received_at"])
