"""Injected/offline batches over conspicuously SYNTHETIC fake data only."""

from copy import deepcopy
import importlib.util

import pytest

from derivative_cases import AS_OF, snapshot


ROOT = "TEST:INDEX"


class FakeProvider:
    """In-memory contract; never contacts a service or loads credentials."""

    def __init__(self, cases=None, *, broken_roots=()):
        self.cases = cases or [snapshot()]
        self.broken_roots = set(broken_roots)
        self.calls = []
        self.packet = {
            "quotes": {case["contract"]["contract_id"]: case["quote"] for case in self.cases},
            "underlyings": {
                f"{case['contract']['venue']}:{case['contract']['root']}": {
                    key: case["underlying"][key]
                    for key in ("underlying_id", "currency", "spot", "spot_observed_at", "retrieved_at")
                }
                for case in self.cases
            },
            "received_at": AS_OF,
        }

    def instrument_records(self, roots):
        self.calls.append(("metadata", list(roots)))
        return [case["contract"] for case in self.cases]

    def underlying_snapshot(self, root, as_of):
        self.calls.append(("history", root, as_of))
        if root in self.broken_roots:
            raise OSError("SYNTHETIC history unavailable")
        return next(case["underlying"] for case in self.cases
                    if f"{case['contract']['venue']}:{case['contract']['root']}" == root)

    def quotes(self, contract_ids, as_of):
        self.calls.append(("quotes", list(contract_ids), as_of))
        return self.packet


def recommend(requests=ROOT, *, kind="futures", provider, as_of=AS_OF, **kwargs):
    assert importlib.util.find_spec("tradeguard.derivative_batches") is not None, "missing offline batch module"
    from tradeguard.derivative_batches import recommend_derivatives

    return recommend_derivatives(requests, kind=kind, provider=provider, as_of=as_of, **kwargs)


def test_history_failure_isolated_without_losing_successful_root():
    provider = FakeProvider(broken_roots={"TEST:OTHER"})
    result = recommend(["test:other", ROOT, "test:index"], provider=provider)

    assert [row["root"] for row in result["results"]] == ["TEST:OTHER", ROOT]
    failed, analyzed = result["results"]
    assert failed["success"] is False
    assert failed["reports"] == []
    assert failed["code"] == "DERIVATIVES_PROVIDER_ERROR"
    assert analyzed["success"] is True
    assert analyzed["status"] == "analyzed"
    report, = analyzed["reports"]
    assert report["success"] is True
    assert report["recommendation"]["score"] is None
    assert report["source"]["provider"] == "injected_offline_provider"
    assert report["source"]["data_mode"] == "user_supplied"
    assert report["source"]["entitlement"] == "unverified"
    assert result["requested_count"] == 3
    assert result["unique_count"] == 2
    assert result["analyzed_count"] == 1
    assert result["failed_count"] == 1
    assert result["eligible_count"] == 0
    assert result["abstained_count"] == 1
    assert result["analyzed_count"] + result["failed_count"] == result["unique_count"]
    assert result["contract_counts"] == {
        "total": 1, "successful": 1, "failed": 0, "eligible": 0, "abstained": 1,
    }
    assert provider.calls == [
        ("metadata", ["TEST:OTHER", ROOT]),
        ("history", "TEST:OTHER", AS_OF),
        ("history", ROOT, AS_OF),
        ("quotes", ["TEST:FUTURE"], AS_OF),
    ]


@pytest.mark.parametrize("changes", [
    {"requests": [ROOT] * 4},
    {"requests": ",".join([ROOT] * 4)},
    {"requests": []}, {"requests": "TEST:ſPY"}, {"requests": "https://TEST:INDEX"},
    {"kind": "future"}, {"kind": []}, {"as_of": "2026-11-10T08:00:00"}, {"as_of": ""},
    {"provider": None}, {"provider": {"instrument_records": []}},
    {"supplemental_by_root": []},
    {"supplemental_by_root": {"TEST:UNREQUESTED": {}}},
    {"supplemental_by_root": {"test:index": {}}},
    {"supplemental_by_root": {ROOT: {}, "TEST:A": {}, "TEST:B": {}, "TEST:C": {}}},
])
def test_preflight_rejects_invalid_arguments_before_any_provider_call(changes):
    provider = FakeProvider()
    arguments = {"provider": provider, **changes}
    result = recommend(**arguments)
    assert result["success"] is False
    assert result["code"] == "INVALID_DERIVATIVE_ARGUMENTS"
    assert result["provider_attempted"] is False
    assert provider.calls == []


def option_case(identifier, *, strike="100", right="call", root="INDEX", currency="USD"):
    case = snapshot("option", contract={
        "contract_id": identifier, "strike": strike, "right": right, "root": root,
        "underlying_id": f"TEST:{root}", "currency": currency,
    }, quote={"contract_id": identifier}, underlying={"underlying_id": f"TEST:{root}", "currency": currency})
    return case


def test_final_spot_rechecks_capped_selection_without_reselection_or_quote_loop():
    cases = [option_case(f"SYNTHETIC:{right}:{strike}", strike=str(strike), right=right)
             for right in ("call", "put") for strike in (95, 98, 99, 100, 101, 102, 105, 106)]
    provider = FakeProvider(cases)
    provider.packet["underlyings"][ROOT]["spot"] = "104"
    selected = [f"SYNTHETIC:{right}:{strike}" for right in ("call", "put") for strike in (100, 99, 101, 98)]
    provider.packet["quotes"] = {key: provider.packet["quotes"][key] for key in selected}
    result = recommend(kind="options", provider=provider)
    row, = result["results"]
    assert provider.calls[-1] == ("quotes", selected, AS_OF)
    assert [call[0] for call in provider.calls] == ["metadata", "history", "quotes"]
    assert row["selection"]["selected_count"] == 8
    assert row["selection"]["exclusion_reasons"] == {"SELECTION_CAP": 6, "STRIKE_OUTSIDE_SPOT_BAND": 2}
    assert row["selection"]["final_exclusion_reasons"] == {"FINAL_STRIKE_OUTSIDE_SPOT_BAND": 2}
    assert len(row["reports"]) == 8
    assert row["success"] is True
    assert row["status"] == "partial"
    assert [report["contract_id"] for report in row["reports"]] == selected
    for report in row["reports"]:
        assert report["recommendation"]["score"] is None
        if report["contract_id"].endswith(":98"):
            assert report["success"] is False
            assert report["code"] == "FINAL_STRIKE_OUTSIDE_SPOT_BAND"
        else:
            assert report["success"] is True
            assert report["metrics"]["option"]["scenarios"][2]["terminal_underlying"] == "104"
    assert result["analyzed_count"] == result["abstained_count"] == 1
    assert result["failed_count"] == result["eligible_count"] == 0
    assert result["contract_counts"] == {
        "total": 8, "successful": 6, "failed": 2, "eligible": 0, "abstained": 6,
    }


@pytest.mark.parametrize("bad_packet", [
    None, [], {},
    {"quotes": [], "underlyings": {}, "received_at": AS_OF},
    {"quotes": {}, "underlyings": [], "received_at": AS_OF},
    {"quotes": {}, "underlyings": {}, "received_at": "2026-11-10T08:00:00"},
    {"quotes": {}, "underlyings": {}, "received_at": AS_OF, "source": {"entitlement": "confirmed"}},
    {"quotes": {"UNREQUESTED": {}}, "underlyings": {}, "received_at": AS_OF},
    {"quotes": {}, "underlyings": {"TEST:UNREQUESTED": {}}, "received_at": AS_OF},
])
def test_malformed_packet_preserves_an_error_report_for_each_selected_contract(bad_packet):
    provider = FakeProvider()
    provider.packet = bad_packet
    result = recommend(provider=provider)
    row, = result["results"]
    report, = row["reports"]
    assert row["selection"]["selected_count"] == 1
    assert row["success"] is False
    assert row["status"] == "failed"
    assert report["success"] is False
    assert report["contract_id"] == "TEST:FUTURE"
    assert report["code"] == "INVALID_DERIVATIVE_PROVIDER_PACKET"
    assert report["recommendation"]["score"] is None
    assert report["source"]["provider"] == "injected_offline_provider"
    assert report["source"]["data_mode"] == "user_supplied"
    assert report["source"]["entitlement"] == "unverified"
    assert result["failed_count"] == 1
    assert result["analyzed_count"] == result["abstained_count"] == 0
    assert result["contract_counts"] == {
        "total": 1, "successful": 0, "failed": 1, "eligible": 0, "abstained": 0,
    }


@pytest.mark.parametrize("refresh", [
    None, {}, [],
    {"underlying_id": ROOT, "currency": "USD", "spot": "100", "spot_observed_at": AS_OF},
    {"underlying_id": "WRONG", "currency": "USD", "spot": "100", "spot_observed_at": AS_OF, "retrieved_at": AS_OF},
    {"underlying_id": ROOT, "currency": "INR", "spot": "100", "spot_observed_at": AS_OF, "retrieved_at": AS_OF},
    {"underlying_id": ROOT, "currency": "USD", "spot": 100.0, "spot_observed_at": AS_OF, "retrieved_at": AS_OF},
    {"underlying_id": ROOT, "currency": "USD", "spot": "0", "spot_observed_at": AS_OF, "retrieved_at": AS_OF},
    {"underlying_id": ROOT, "currency": "USD", "spot": "100", "spot_observed_at": AS_OF, "retrieved_at": AS_OF, "bars": []},
])
def test_bad_or_missing_refresh_cannot_fall_back_to_old_spot_and_other_root_survives(refresh):
    other = snapshot(contract={"contract_id": "OTHER:FUTURE", "root": "OTHER", "underlying_id": "TEST:OTHER"},
                     quote={"contract_id": "OTHER:FUTURE"}, underlying={"underlying_id": "TEST:OTHER"})
    provider = FakeProvider([snapshot(), other])
    if refresh is None:
        del provider.packet["underlyings"][ROOT]
    else:
        provider.packet["underlyings"][ROOT] = refresh
    result = recommend([ROOT, "TEST:OTHER"], provider=provider)
    failed, succeeded = result["results"]
    assert failed["success"] is False
    assert failed["reports"][0]["success"] is False
    assert failed["reports"][0]["contract_id"] == "TEST:FUTURE"
    assert succeeded["success"] is True
    assert result["analyzed_count"] == result["failed_count"] == 1
    assert result["contract_counts"]["successful"] == result["contract_counts"]["failed"] == 1


@pytest.mark.parametrize("bad_quote", [None, {}, [], {"contract_id": "WRONG"}])
def test_one_missing_or_malformed_selected_quote_keeps_its_error_row(bad_quote):
    provider = FakeProvider([option_case("SYNTHETIC:one"), option_case("SYNTHETIC:two", strike="101")])
    if bad_quote is None:
        del provider.packet["quotes"]["SYNTHETIC:one"]
    else:
        provider.packet["quotes"]["SYNTHETIC:one"] = bad_quote
    result = recommend(kind="options", provider=provider)
    row, = result["results"]
    first, second = row["reports"]
    assert first["contract_id"] == "SYNTHETIC:one"
    assert first["success"] is False
    assert second["contract_id"] == "SYNTHETIC:two"
    assert second["success"] is True
    assert row["status"] == "partial"
    assert result["analyzed_count"] == result["abstained_count"] == 1
    assert result["failed_count"] == 0
    assert result["contract_counts"] == {
        "total": 2, "successful": 1, "failed": 1, "eligible": 0, "abstained": 1,
    }


def supplemental(cases):
    result = {}
    for case in cases:
        contract = case["contract"]
        root = f"{contract['venue']}:{contract['root']}"
        entry = result.setdefault(root, {"rates": deepcopy(case["rates"]),
                                         "margin_by_contract": {}, "costs_by_contract": {}})
        entry["rates"].update(underlying_id=contract["underlying_id"], currency=contract["currency"])
        for name in ("margin", "costs"):
            evidence = deepcopy(case[name])
            evidence.update(contract_id=contract["contract_id"], currency=contract["currency"])
            entry[name + "_by_contract"][contract["contract_id"]] = evidence
    return result


@pytest.mark.parametrize("kind", ["futures", "options"])
def test_bound_supplemental_evidence_reaches_analyzer_without_caller_mutation(kind):
    cases = [snapshot("option" if kind == "options" else "future")]
    evidence = supplemental(cases)
    provider = FakeProvider(cases)
    before = deepcopy((cases, evidence, provider.packet))
    result = recommend(kind=kind, provider=provider, supplemental_by_root=evidence)
    report = result["results"][0]["reports"][0]
    assert report["success"] is True
    assert report["evidence_coverage"]["checks"]["cost_estimate"] is True
    if kind == "futures":
        metrics = report["metrics"]["futures"]
        assert metrics["margin_reference"] == evidence[ROOT]["margin_by_contract"]["TEST:FUTURE"]
        assert metrics["scenarios"][2]["long_net_pnl_after_supplied_costs"] == "-1.625"
    else:
        assert report["metrics"]["option"]["pricing"]["status"] == "available"
    assert report["recommendation"]["score"] is None
    assert (cases, evidence, provider.packet) == before


@pytest.mark.parametrize("name,kind", [("costs", "futures"), ("margin", "futures"), ("rates", "options")])
def test_stale_supplemental_evidence_never_receives_an_attractive_fallback(name, kind):
    cases = [snapshot("option" if kind == "options" else "future")]
    evidence = supplemental(cases)
    if name == "rates":
        evidence[ROOT]["rates"]["as_of"] = "2026-01-01T00:00:00Z"
    else:
        evidence[ROOT][name + "_by_contract"][cases[0]["contract"]["contract_id"]]["as_of"] = "2026-01-01T00:00:00Z"
    result = recommend(kind=kind, provider=FakeProvider(cases), supplemental_by_root=evidence)
    report = result["results"][0]["reports"][0]
    assert report["success"] is True
    assert "STALE_" + name.upper() in report["blockers"]
    check = {"costs": "cost_estimate", "margin": "margin_reference", "rates": "rates"}[name]
    assert report["evidence_coverage"]["checks"][check] is False
    if name == "costs":
        assert all(row["long_net_pnl_after_supplied_costs"] is None for row in report["metrics"]["futures"]["scenarios"])
    elif name == "margin":
        assert report["metrics"]["futures"]["margin_reference"] is None
    else:
        assert report["metrics"]["option"]["pricing"]["iv_midpoint"] is None
    assert report["recommendation"]["score"] is None


@pytest.mark.parametrize("entry", [
    None, [], {"source": {"data_mode": "provider", "entitlement": "confirmed"}},
    {"costs_by_contract": []}, {"margin_by_contract": None},
    {"costs_by_contract": {"TEST:UNSELECTED": {}}},
    {"costs_by_contract": {ROOT: {}}}, {"margin_by_contract": {"test:future": {}}},
    {"rates_by_underlying": {ROOT: {}}},
])
def test_unbound_or_unknown_supplemental_keys_are_errors_not_missing_evidence(entry):
    result = recommend(provider=FakeProvider(), supplemental_by_root={ROOT: entry})
    row, = result["results"]
    report, = row["reports"]
    assert row["success"] is False
    assert report["success"] is False
    assert report["code"] == "INVALID_DERIVATIVE_SUPPLEMENTAL"
    assert report["contract_id"] == "TEST:FUTURE"
    assert report["metrics"] == {}
    assert result["failed_count"] == 1


def test_omitted_cutoff_is_captured_after_final_fetch_not_at_request_start(monkeypatch):
    from datetime import datetime, timezone
    from tradeguard import derivative_batches

    provider = FakeProvider()

    class FetchClock:
        @staticmethod
        def now(tz):
            assert tz is timezone.utc
            time = AS_OF if provider.calls and provider.calls[-1][0] == "quotes" else "2026-11-10T07:59:50Z"
            return datetime.fromisoformat(time.replace("Z", "+00:00"))

    monkeypatch.setattr(derivative_batches, "datetime", FetchClock)
    result = recommend(provider=provider, as_of=None)
    report = result["results"][0]["reports"][0]
    assert report["success"] is True
    assert result["as_of"] == report["as_of"] == "2026-11-10T08:00:00+00:00"
    assert not any(blocker.startswith("FUTURE_") for blocker in report["blockers"])
    assert provider.calls[-1] == ("quotes", ["TEST:FUTURE"], None)


def test_comparison_groups_never_cross_root_currency_family_or_option_right():
    cases = [option_case(f"SYNTHETIC:{root}:{right}:{strike}", root=root, right=right, strike=str(strike), currency=currency)
             for root, currency in (("INDEX", "USD"), ("OTHER", "INR"))
             for right in ("call", "put") for strike in (100, 101)]
    result = recommend(["TEST:OTHER", ROOT], kind="options", provider=FakeProvider(cases))
    assert result["analyzed_count"] == result["abstained_count"] == 2
    assert result["eligible_count"] == result["failed_count"] == 0
    assert result["contract_counts"]["total"] == result["contract_counts"]["abstained"] == 8
    for row, currency in zip(result["results"], ("INR", "USD")):
        groups = row["comparisons"]
        assert len(groups) == 2
        assert [group["right"] for group in groups] == ["call", "put"]
        for group in groups:
            assert group["root"] == row["root"]
            assert group["currency"] == currency
            assert group["family"] == "index_option"
            assert group["ranking_status"] == "unavailable_offline_scores"
            assert len(group["rows"]) == 2
            for comparison in group["rows"]:
                report = next(item for item in row["reports"] if item["contract_id"] == comparison["contract_id"])
                assert report["contract"]["right"] == group["right"]
                assert comparison["score"] is None
                assert comparison["rank"] is None
        assert all(report["strategy"] in ("long_call", "long_put") for report in row["reports"])
        assert not any("legs" in report for report in row["reports"])


@pytest.mark.parametrize("records", [None, {}, (), iter([]), [None] * 1001])
def test_malformed_or_unbounded_metadata_fails_all_roots_before_history(records):
    class BadMetadata(FakeProvider):
        def instrument_records(self, roots):
            super().instrument_records(roots)
            return records

    provider = BadMetadata()
    result = recommend([ROOT, "TEST:OTHER"], provider=provider)
    assert provider.calls == [("metadata", [ROOT, "TEST:OTHER"])]
    assert result["analyzed_count"] == 0
    assert result["failed_count"] == result["unique_count"] == 2
    assert result["contract_counts"]["total"] == 0
    assert all(row["code"] == "INVALID_DERIVATIVE_PROVIDER_METADATA" for row in result["results"])


@pytest.mark.parametrize("stage", ["metadata", "quotes"])
def test_provider_exception_is_contained_with_truthful_root_and_contract_counts(stage):
    class BrokenProvider(FakeProvider):
        def instrument_records(self, roots):
            value = super().instrument_records(roots)
            if stage == "metadata":
                raise OSError("SYNTHETIC metadata failure")
            return value

        def quotes(self, contract_ids, as_of):
            super().quotes(contract_ids, as_of)
            raise OSError("SYNTHETIC quote failure")

    result = recommend(provider=BrokenProvider())
    row, = result["results"]
    assert row["success"] is False
    assert result["failed_count"] == result["unique_count"] == 1
    assert result["analyzed_count"] == result["abstained_count"] == 0
    if stage == "metadata":
        assert row["code"] == "DERIVATIVES_PROVIDER_ERROR"
        assert row["reports"] == []
        assert result["contract_counts"]["total"] == 0
    else:
        assert len(row["reports"]) == 1
        assert row["reports"][0]["code"] == "DERIVATIVES_PROVIDER_ERROR"
        assert result["contract_counts"]["total"] == result["contract_counts"]["failed"] == 1


@pytest.mark.parametrize("problem", ["missing_clock", "unknown", "too_many_bars", "cycle"])
def test_history_packet_is_bounded_and_canonical_before_copy_or_selection(problem):
    provider = FakeProvider()
    history = provider.cases[0]["underlying"]
    if problem == "missing_clock":
        del history["spot_observed_at"]
    elif problem == "unknown":
        history["trusted_source"] = True
    elif problem == "too_many_bars":
        history["bars"] = [{}] * 2001
    else:
        history["bars"] = [history]
    result = recommend(provider=provider)
    row, = result["results"]
    assert row["success"] is False
    assert row["selection"] is None
    assert row["reports"] == []
    assert row["code"] == "INVALID_DERIVATIVE_PROVIDER_HISTORY"
    assert [call[0] for call in provider.calls] == ["metadata", "history"]


def test_refresh_cannot_launder_an_original_history_retrieval_or_finalization_clock():
    provider = FakeProvider()
    provider.cases[0]["underlying"]["retrieved_at"] = "2026-11-08T08:00:00Z"
    result = recommend(provider=provider)
    row, = result["results"]
    assert row["success"] is False
    assert not any(report["success"] for report in row["reports"])


def test_no_eligible_contract_is_an_explicit_root_failure_without_quote_call():
    provider = FakeProvider([snapshot(contract={"last_trade_at": AS_OF})])
    result = recommend(provider=provider)
    row, = result["results"]
    assert row["success"] is False
    assert row["code"] == "NO_ELIGIBLE_DERIVATIVE_CONTRACTS"
    assert row["selection"]["selected_count"] == 0
    assert row["selection"]["excluded_count"] == 1
    assert row["reports"] == []
    assert result["failed_count"] == result["unique_count"] == 1
    assert result["contract_counts"]["total"] == 0
    assert result["provider_attempted"] is True
    assert [call[0] for call in provider.calls] == ["metadata", "history"]


def test_batch_partial_status_retains_a_single_roots_selected_contract_failure():
    provider = FakeProvider([option_case("SYNTHETIC:one"), option_case("SYNTHETIC:two", strike="101")])
    del provider.packet["quotes"]["SYNTHETIC:one"]
    result = recommend(kind="options", provider=provider)
    assert result["success"] is True
    assert result["status"] == "partial"
    assert result["analyzed_count"] == result["unique_count"] == 1
    assert result["failed_count"] == 0


def test_no_selection_still_captures_omitted_final_cutoff_after_history(monkeypatch):
    from datetime import datetime
    from tradeguard import derivative_batches

    provider = FakeProvider([snapshot(contract={"last_trade_at": AS_OF})])

    class FetchClock:
        @staticmethod
        def now(tz):
            time = "2026-11-10T08:00:01Z" if provider.calls else AS_OF
            return datetime.fromisoformat(time.replace("Z", "+00:00"))

    monkeypatch.setattr(derivative_batches, "datetime", FetchClock)
    result = recommend(provider=provider, as_of=None)
    assert result["as_of"] == "2026-11-10T08:00:01+00:00"


def test_preflight_failure_cannot_claim_a_different_ingress_mode():
    result = recommend("invalid", provider=FakeProvider())
    assert result["source"]["provider"] == "injected_offline_provider"
    assert result["source"]["data_mode"] == result["data_mode"] == "user_supplied"
    assert result["source"]["entitlement"] == "unverified"
    assert result["source"]["retrieved_at"] is None


def test_three_option_roots_fetch_at_most_24_quotes_and_return_no_raw_bars():
    import json

    cases = [option_case(f"SYNTHETIC:{root}:{right}:{strike}", root=root, right=right, strike=str(strike))
             for root in ("ONE", "TWO", "THREE") for right in ("call", "put") for strike in (98, 99, 100, 101)]
    provider = FakeProvider(cases)
    before = deepcopy(cases)
    roots = ["TEST:THREE", "TEST:ONE", "TEST:TWO"]
    result = recommend(roots, kind="options", provider=provider)
    assert roots == ["TEST:THREE", "TEST:ONE", "TEST:TWO"]
    assert [row["root"] for row in result["results"]] == roots
    assert result["analyzed_count"] == result["unique_count"] == result["abstained_count"] == 3
    assert result["failed_count"] == result["eligible_count"] == 0
    assert result["contract_counts"] == {"total": 24, "successful": 24, "failed": 0, "eligible": 0, "abstained": 24}
    assert [call[0] for call in provider.calls] == ["metadata", "history", "history", "history", "quotes"]
    assert len(provider.calls[-1][1]) == 24
    assert len(set(provider.calls[-1][1])) == 24
    assert cases == before
    assert '"bars"' not in json.dumps(result, allow_nan=False)

    def scores(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "score":
                    yield child
                yield from scores(child)
        elif isinstance(value, list):
            for child in value:
                yield from scores(child)

    found = list(scores(result))
    assert found and all(score is None for score in found)


@pytest.mark.parametrize("field,value,blocker", [
    ("spot_observed_at", "2026-11-10T07:59:30Z", "STALE_SPOT"),
    ("spot_observed_at", "2026-11-10T08:00:01Z", "FUTURE_SPOT_CLOCK"),
    ("retrieved_at", "2026-11-10T08:00:01Z", "SOURCE_CLOCK_ORDER"),
])
def test_refreshed_spot_clocks_are_revalidated_by_the_real_analyzer(field, value, blocker):
    provider = FakeProvider()
    provider.packet["underlyings"][ROOT][field] = value
    result = recommend(provider=provider)
    report = result["results"][0]["reports"][0]
    assert report["success"] is True
    assert blocker in report["blockers"]
    assert report["evidence_coverage"]["checks"]["quote_evidence"] is False
    assert all(item["score"] is None for item in report["recommendations"].values())
    assert result["as_of"] == report["as_of"] == "2026-11-10T08:00:00+00:00"


def test_failed_metadata_fetch_also_uses_the_final_omitted_cutoff(monkeypatch):
    from datetime import datetime
    from tradeguard import derivative_batches

    class FailedMetadata(FakeProvider):
        def instrument_records(self, roots):
            super().instrument_records(roots)
            raise OSError("SYNTHETIC metadata failure")

    provider = FailedMetadata()

    class FetchClock:
        @staticmethod
        def now(tz):
            time = "2026-11-10T08:00:01Z" if provider.calls else AS_OF
            return datetime.fromisoformat(time.replace("Z", "+00:00"))

    monkeypatch.setattr(derivative_batches, "datetime", FetchClock)
    result = recommend(provider=provider, as_of=None)
    assert result["as_of"] == "2026-11-10T08:00:01+00:00"
    assert result["failed_count"] == 1


def test_future_batch_quotes_only_the_single_selected_contract_from_1000_records():
    identifier = " 000017/CaSe " + "x" * 80
    case = snapshot(contract={"contract_id": identifier}, quote={"contract_id": identifier})

    class ManyFutures(FakeProvider):
        def instrument_records(self, roots):
            first, = super().instrument_records(roots)
            return [first] + [{**first, "contract_id": f"SYNTHETIC:{index:04d}"} for index in range(999)]

    provider = ManyFutures([case])
    result = recommend(provider=provider, supplemental_by_root=supplemental([case]))
    row, = result["results"]
    report, = row["reports"]
    assert provider.calls[-1] == ("quotes", [identifier], AS_OF)
    assert row["selection"]["searched_count"] == 1000
    assert row["selection"]["selected_count"] == 1
    assert row["selection"]["exclusion_reasons"] == {"SELECTION_CAP": 999}
    assert report["success"] is True
    assert report["contract_id"] == report["contract"]["contract_id"] == identifier
    assert report["evidence_coverage"]["checks"]["cost_estimate"] is True
    assert result["contract_counts"]["total"] == 1
    assert report["recommendation"]["score"] is None


def test_batch_source_preserves_real_packet_receipt_not_the_analysis_cutoff():
    provider = FakeProvider([snapshot(underlying={"retrieved_at": "2026-11-10T07:59:59Z"})])
    provider.packet["received_at"] = "2026-11-10T07:59:59Z"
    result = recommend(provider=provider)
    report = result["results"][0]["reports"][0]
    assert report["success"] is True
    assert result["as_of"] == "2026-11-10T08:00:00+00:00"
    assert result["source"]["retrieved_at"] == report["source"]["retrieved_at"] == "2026-11-10T07:59:59Z"


def test_batch_without_a_valid_quote_packet_has_no_fabricated_source_receipt():
    provider = FakeProvider()
    provider.packet = {}
    result = recommend(provider=provider)
    assert result["source"]["retrieved_at"] is None
