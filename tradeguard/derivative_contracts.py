"""Pure, bounded input contracts for offline derivatives research.

No network, accounts, trusted-adapter escape hatches, or execution are provided.
Exact money values never pass through binary floats. Successful validation is
not certification of a source, an executable quote, or financial performance.

Normalization preserves original JSON values/IDs/clocks and omitted optional
objects; only source.data_mode/entitlement are downgraded and _validation is
added. _validation.usable contains rates/costs/margin/history/quote booleans.
These describe internally usable evidence, NOT trusted provenance or eligibility;
all offline results carry OFFLINE_PROVENANCE_UNVERIFIED. Optional objects may be
omitted/null; missing r/q values remain missing. Rates TTL is 7 days, costs 24
hours, margin 1 hour (inclusive); future-dated evidence is unusable. Missing or
stale costs block all families; rates block options; margin blocks futures.

Quote volume/open_interest, if supplied, are source-labelled objects with exact
keys {value: nonnegative integer, unit: 'contracts', source, as_of: aware clock}.
They are descriptive only, never signed directional evidence. Crossed, nonpositive
or off-tick bid/ask fail structurally. Other quote eligibility defects are blockers.

Bounds: 2,000 bars, 16 MiB compact serialized JSON, 30,000 tree nodes, depth 8,
32 keys/object, 2,048 characters/string (IDs/sources 256), 32 cost exclusions.
Cash-index OHLC accepts finite numeric int/float in [1e-30, 1e30], with volume
in [0, 1e30]. Daily spacing rejects gaps >7 days or median gap >3 days over
at least three observations. This is a conservative sparse-history check, not
exchange-calendar certification. Supplied finalization/session evidence remains
unverified. Timestamp text uses YYYY-MM-DDTHH:MM:SS[.ffffff](Z|+/-HH:MM).
"""

from decimal import Decimal, InvalidOperation
import re


INVALID = "INVALID_DERIVATIVE_SNAPSHOT"
UNSUPPORTED = "UNSUPPORTED_INSTRUMENT"
_DECIMAL = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?", re.ASCII)


class DerivativeInputError(ValueError):
    """An explicit structural/unsupported-input error with a stable code."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def decimal_value(value):
    """Return an exact finite Decimal, bounded in size, magnitude and scale.

    Strings use plain ASCII notation (no exponent/whitespace); integers and
    Decimal instances are accepted, but floats and booleans are never money.
    Decimal input also has at most 100 coefficient digits, exponent -100..30,
    and absolute magnitude <=1e30. No context-sensitive normalization is used.
    """
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise DerivativeInputError(INVALID, "expected an exact decimal string or integer")
    if isinstance(value, str) and (len(value) > 100 or _DECIMAL.fullmatch(value) is None):
        raise DerivativeInputError(INVALID, "invalid or excessive decimal representation")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise DerivativeInputError(INVALID, "invalid decimal") from exc
    if not result.is_finite():
        raise DerivativeInputError(INVALID, "finite decimal required")
    parts = result.as_tuple()
    if (len(parts.digits) > 100 or not -100 <= parts.exponent <= 30
            or result.copy_abs() > Decimal("1e30")):
        raise DerivativeInputError(INVALID, "excessive decimal magnitude or scale")
    return result


def aware_time(value):
    """Parse a bounded, timezone-aware ISO timestamp and return UTC."""
    from datetime import datetime, timezone

    if (not isinstance(value, str) or len(value) > 40
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
                            r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])", value, re.ASCII) is None):
        raise DerivativeInputError(INVALID, "expected aware ISO timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError("naive timestamp")
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise DerivativeInputError(INVALID, "invalid or naive timestamp") from exc


def contract_quantity(value):
    """Validate a bounded whole number of contracts, never broker order units."""
    if type(value) is not int or not 1 <= value <= 100:
        raise DerivativeInputError(INVALID, "contracts must be an integer in 1..100")
    return value


_ROOT = re.compile(r"[A-Za-z][A-Za-z0-9]{1,7}:[A-Za-z][A-Za-z0-9]{0,19}", re.ASCII)


def parse_root_requests(value):
    """Validate <=3 ASCII root tokens before normalization and stable dedupe."""
    if isinstance(value, str):
        if (len(value) > 256 or not value.isascii()
                or any(ord(char) < 32 and char not in "\t\r\n" for char in value)):
            raise DerivativeInputError(INVALID, "root request must be ASCII and <=256 characters")
        tokens = re.split(r"[\s,]+", value.strip()) if value.strip() else []
    elif isinstance(value, list):
        if len(value) > 3:
            raise DerivativeInputError(INVALID, "provide 1..3 venue:root tokens")
        tokens = list(value)
    else:
        raise DerivativeInputError(INVALID, "expected root string or list")
    if not 1 <= len(tokens) <= 3:
        raise DerivativeInputError(INVALID, "provide 1..3 venue:root tokens")
    if any(not isinstance(token, str) or _ROOT.fullmatch(token) is None for token in tokens):
        raise DerivativeInputError(INVALID, "invalid root; use ASCII VENUE:ROOT")
    return {"requested": tokens, "roots": list(dict.fromkeys(token.upper() for token in tokens))}


def _error(message):
    raise DerivativeInputError(INVALID, message)


def _text(value, name, *, limit=256):
    import unicodedata

    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(unicodedata.category(char) in ("Cc", "Cf", "Cs") for char in value)):
        _error(f"{name} must be nonempty bounded text without controls")
    return value


def _object(value, name):
    if not isinstance(value, dict):
        _error(f"{name} must be an object")
    return value


def validate_snapshot(snapshot, *, as_of):
    """Validate and deep-copy one offline snapshot; never trust caller provenance."""
    from copy import deepcopy

    validation = {"blockers": [], "missing_data": [], "warnings": [],
                  "usable": dict.fromkeys(("rates", "costs", "margin", "history", "quote"), False)}
    cutoff = aware_time(as_of)
    _bounded_json(snapshot)
    data = _object(snapshot, "snapshot")
    required = {"schema_version", "contract", "quote", "underlying", "source"}
    if not required <= data.keys() or data.keys() - required - {"rates", "margin", "costs"}:
        _error("missing or unknown snapshot fields")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        _error("schema_version must be integer 1")
    contract = _object(data["contract"], "contract")
    quote = _object(data["quote"], "quote")
    underlying = _object(data["underlying"], "underlying")
    _object(data["source"], "source")
    family = _text(contract.get("family"), "contract.family")
    if family not in ("index_future", "index_option"):
        raise DerivativeInputError(UNSUPPORTED, "unsupported instrument family")
    contract_fields = {"contract_id", "venue", "root", "family", "underlying_id", "currency", "value_per_price_unit",
                       "tick_size", "last_trade_at", "expiry_at", "settlement", "spec_source", "spec_effective_at",
                       "standard_deliverable"}
    if family == "index_option":
        contract_fields |= {"right", "strike", "exercise", "underlying_kind"}
    _fields(contract, contract_fields, set(), "contract")
    _fields(quote, {"contract_id", "bid", "ask", "bid_contracts", "ask_contracts", "observed_at", "received_at",
                    "delay_seconds", "market_state"}, {"volume", "open_interest"}, "quote")
    _fields(underlying, {"underlying_id", "currency", "spot", "spot_observed_at", "interval", "price_basis",
                         "adjustment", "source", "retrieved_at", "bars", "last_bar_finalized_at"}, set(), "underlying")
    _fields(data["source"], {"provider", "retrieved_at", "data_mode", "entitlement", "historical_vintage"}, set(), "source")
    venue = _text(contract["venue"], "contract.venue")
    root = _text(contract["root"], "contract.root")
    if _ROOT.fullmatch(f"{venue}:{root}") is None:
        _error("contract venue/root must form an ASCII VENUE:ROOT")
    contract_id = _text(contract.get("contract_id"), "contract_id")
    underlying_id = _text(contract.get("underlying_id"), "underlying_id")
    if quote.get("contract_id") != contract_id or underlying.get("underlying_id") != underlying_id:
        _error("quote/underlying identity mismatch")
    currency = _text(contract.get("currency"), "contract.currency")
    if re.fullmatch(r"[A-Z]{3}", currency, re.ASCII) is None:
        _error("currency must be an uppercase three-letter code")
    if underlying.get("currency") != currency:
        _error("underlying currency mismatch")
    for field in ("value_per_price_unit", "tick_size"):
        if decimal_value(contract.get(field)) <= 0:
            _error(f"{field} must be positive")
    for name, identity, expected in (("rates", "underlying_id", underlying_id),
                                     ("margin", "contract_id", contract_id),
                                     ("costs", "contract_id", contract_id)):
        if name in data and data[name] is not None:
            evidence = _object(data[name], name)
            if evidence.get("currency") != currency or evidence.get(identity) != expected:
                _error(f"{name} currency/identity mismatch")
    from decimal import localcontext
    with localcontext() as context:
        context.prec = 256
        tick = decimal_value(contract["tick_size"])
        for field in ("bid", "ask"):
            if decimal_value(quote.get(field)) % tick:
                _error(f"quote.{field} is off tick grid")
    family = contract.get("family")
    if (family not in ("index_future", "index_option") or contract.get("settlement") != "cash"
            or contract.get("standard_deliverable") is not True):
        raise DerivativeInputError(UNSUPPORTED, "only standard cash-settled index contracts are supported")
    if family == "index_option":
        if contract.get("exercise") != "european" or contract.get("underlying_kind") != "cash_index":
            raise DerivativeInputError(UNSUPPORTED, "only European options on a cash index are supported")
        if contract.get("right") not in ("call", "put") or decimal_value(contract.get("strike")) <= 0:
            _error("option right/positive strike required")
    last_trade = aware_time(contract.get("last_trade_at"))
    expiry = aware_time(contract.get("expiry_at"))
    if last_trade > expiry:
        _error("last_trade_at must not follow expiry_at")
    if cutoff >= last_trade:
        validation["blockers"].append("EXPIRED_CONTRACT")
    _text(contract.get("spec_source"), "spec_source")
    if aware_time(contract.get("spec_effective_at")) > cutoff:
        validation["blockers"].append("FUTURE_SPEC_EFFECTIVE_AT")
    quote_blockers = []
    bid, ask = decimal_value(quote.get("bid")), decimal_value(quote.get("ask"))
    if not 0 < bid <= ask:
        _error("positive non-crossed bid and ask required")
    for field in ("bid_contracts", "ask_contracts"):
        value = quote.get(field)
        if type(value) is not int or not 0 <= value <= 10**12:
            _error(f"{field} must be a bounded nonnegative integer of contracts")
        if value < 1 and "INSUFFICIENT_DEPTH" not in quote_blockers:
            quote_blockers.append("INSUFFICIENT_DEPTH")
    delay = quote.get("delay_seconds")
    if delay is None:
        quote_blockers.append("QUOTE_DELAY_UNKNOWN")
    elif type(delay) is not int or not 0 <= delay <= 10**9:
        _error("delay_seconds must be a bounded nonnegative integer or null")
    elif delay:
        quote_blockers.append("DELAYED_QUOTE")
    state = quote.get("market_state")
    if state not in ("open", "closed", "unknown"):
        _error("invalid market_state")
    if state != "open":
        quote_blockers.append("MARKET_CLOSED" if state == "closed" else "MARKET_STATE_UNKNOWN")
    observed, received = aware_time(quote.get("observed_at")), aware_time(quote.get("received_at"))
    if observed > received:
        quote_blockers.append("QUOTE_CLOCK_ORDER")
    if observed > cutoff or received > cutoff:
        quote_blockers.append("FUTURE_QUOTE_CLOCK")
    if (cutoff - observed).total_seconds() > 15 or (cutoff - received).total_seconds() > 15:
        quote_blockers.append("STALE_QUOTE")
    spot_time = aware_time(underlying.get("spot_observed_at"))
    if abs((spot_time - observed).total_seconds()) > 5:
        quote_blockers.append("SPOT_QUOTE_SKEW")
    if spot_time > cutoff:
        quote_blockers.append("FUTURE_SPOT_CLOCK")
    if (cutoff - spot_time).total_seconds() > 15:
        quote_blockers.append("STALE_SPOT")
    for name in ("volume", "open_interest"):
        statistic = quote.get(name)
        if statistic is not None:
            _fields(statistic, {"value", "unit", "source", "as_of"}, set(), f"quote.{name}")
            if type(statistic["value"]) is not int or not 0 <= statistic["value"] <= 10**12:
                _error(f"quote.{name}.value must be a bounded nonnegative integer")
            if statistic["unit"] != "contracts":
                _error(f"quote.{name}.unit must explicitly be contracts")
            _text(statistic["source"], f"quote.{name}.source")
            if aware_time(statistic["as_of"]) > cutoff and "FUTURE_QUOTE_STATISTIC_CLOCK" not in quote_blockers:
                quote_blockers.append("FUTURE_QUOTE_STATISTIC_CLOCK")
    validation["blockers"].extend(quote_blockers)
    validation["usable"]["quote"] = not quote_blockers
    _validate_history(underlying, cutoff, validation)
    underlying_receipt = aware_time(underlying["retrieved_at"])
    if spot_time > underlying_receipt:
        validation["blockers"].append("UNDERLYING_CLOCK_ORDER")
        validation["usable"]["quote"] = False
    if underlying_receipt > cutoff:
        validation["usable"]["quote"] = False
    source = data["source"]
    _text(source.get("provider"), "source.provider")
    _text(source.get("historical_vintage"), "source.historical_vintage", limit=2048)
    mode, entitlement = source.get("data_mode"), source.get("entitlement")
    if mode not in ("fixture", "user_supplied", "provider") or entitlement not in ("unverified", "confirmed"):
        _error("invalid source data_mode/entitlement")
    source_time = aware_time(source.get("retrieved_at"))
    if source_time > cutoff:
        validation["blockers"].append("FUTURE_SOURCE_CLOCK")
        validation["usable"]["quote"] = False
        validation["usable"]["history"] = False
    if source_time < received:
        validation["blockers"].append("SOURCE_CLOCK_ORDER")
        validation["usable"]["quote"] = False
    if source_time < underlying_receipt:
        if "SOURCE_CLOCK_ORDER" not in validation["blockers"]:
            validation["blockers"].append("SOURCE_CLOCK_ORDER")
        validation["usable"]["history"] = False
    _validate_optional(data, cutoff, validation)
    validation["blockers"].append("OFFLINE_PROVENANCE_UNVERIFIED")
    validation["warnings"].append("CALLER_SOURCE_AND_SESSION_EVIDENCE_UNVERIFIED")
    if mode == "provider" or entitlement == "confirmed":
        validation["warnings"].append("OFFLINE_SOURCE_ASSERTIONS_IGNORED")
    result = deepcopy(data)
    result["source"]["data_mode"] = "fixture" if mode == "fixture" else "user_supplied"
    result["source"]["entitlement"] = "unverified"
    result["_validation"] = validation
    return result


def _cash_number(value, name, *, zero=False):
    import math

    if type(value) not in (int, float) or not (0 <= value <= 1e30) or not math.isfinite(value):
        _error(f"{name} must be a finite bounded cash-index number")
    if not zero and value < 1e-30:
        _error(f"{name} must be positive")
    return value


def _validate_history(underlying, cutoff, validation):
    from datetime import date
    from statistics import median

    if (underlying.get("interval") != "1d" or underlying.get("price_basis") != "price_index"
            or underlying.get("adjustment") != "raw"):
        _error("underlying must be completed raw daily price-index history")
    if decimal_value(underlying.get("spot")) <= 0:
        _error("cash-index spot must be positive")
    source = _text(underlying.get("source"), "underlying.source")
    retrieved = aware_time(underlying.get("retrieved_at"))
    finalized = aware_time(underlying.get("last_bar_finalized_at"))
    if finalized > cutoff or finalized > retrieved:
        _error("unfinished history: finalization must be <=retrieval and cutoff")
    bars = underlying.get("bars")
    if not isinstance(bars, list) or len(bars) > 2000:
        _error("underlying.bars must be a list of at most 2000 bars")
    dates = []
    for bar in bars:
        _fields(bar, {"date", "open", "high", "low", "close", "volume"}, {"source"}, "bar")
        day = bar.get("date")
        if not isinstance(day, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day) is None:
            _error("bar.date must be YYYY-MM-DD")
        try:
            day = date.fromisoformat(day)
        except ValueError as exc:
            raise DerivativeInputError(INVALID, "invalid bar.date") from exc
        if (dates and day <= dates[-1]) or day > finalized.date() or day > cutoff.date():
            _error("bars must be completed, uniquely dated and increasing")
        dates.append(day)
        prices = [_cash_number(bar.get(key), f"bar.{key}") for key in ("open", "high", "low", "close")]
        opening, high, low, close = prices
        if not low <= min(opening, close) <= max(opening, close) <= high:
            _error("inconsistent OHLC")
        _cash_number(bar.get("volume"), "bar.volume", zero=True)
        if "source" in bar and _text(bar["source"], "bar.source") != source:
            _error("bar source differs from underlying source")
    gaps = [(right - left).days for left, right in zip(dates, dates[1:])]
    if gaps and (max(gaps) > 7 or (len(gaps) >= 2 and median(gaps) > 3)):
        _error("sparse non-daily history cannot masquerade as daily")
    history_blockers = []
    if len(bars) < 200:
        history_blockers.append("INSUFFICIENT_HISTORY")
        validation["missing_data"].append("HISTORY_200_DAILY_BARS")
    if retrieved > cutoff:
        history_blockers.append("FUTURE_UNDERLYING_CLOCK")
    if dates and (cutoff.date() - dates[-1]).days > 7:
        history_blockers.append("STALE_HISTORY")
    validation["blockers"].extend(history_blockers)
    validation["usable"]["history"] = not history_blockers


def _fields(value, required, optional, name):
    _object(value, name)
    if not required <= value.keys() or value.keys() - required - optional:
        _error(f"missing or unknown {name} fields")


def _validate_optional(data, cutoff, validation):
    family = data["contract"]["family"]
    common = {"currency", "as_of", "source"}
    specifications = (
        ("rates", 7 * 86400, common | {"underlying_id", "compounding", "day_count"},
         {"risk_free", "dividend_yield"}),
        ("costs", 86400, common | {"contract_id", "round_trip_per_contract", "excludes"}, set()),
        ("margin", 3600, common | {"contract_id", "amount_per_contract", "scope", "account_specific"}, set()),
    )
    for name, ttl, required, optional in specifications:
        relevant = name == "costs" or (name == "margin" and family == "index_future") or (
            name == "rates" and family == "index_option")
        problems = []
        evidence = data.get(name)
        if evidence is None:
            problems.append(name.upper())
        else:
            _fields(evidence, required, optional, name)
            _text(evidence["source"], f"{name}.source")
            if name == "rates":
                if evidence["compounding"] != "continuous" or evidence["day_count"] != "ACT/365F":
                    _error("rates require continuous compounding and ACT/365F")
                for field, gap, low, high in (("risk_free", "RISK_FREE_RATE", -1, 1),
                                               ("dividend_yield", "DIVIDEND_YIELD", 0, 1)):
                    if field not in evidence or evidence[field] is None:
                        problems.append(gap)
                    elif not low <= decimal_value(evidence[field]) <= high:
                        _error(f"rates.{field} outside supported model bounds")
            elif name == "margin":
                if (evidence["scope"] not in ("exchange_reference", "broker_reference")
                        or evidence["account_specific"] is not False):
                    _error("margin must be a non-account-specific exchange/broker reference")
                if decimal_value(evidence["amount_per_contract"]) <= 0:
                    _error("positive margin amount_per_contract required")
            else:
                if decimal_value(evidence["round_trip_per_contract"]) < 0:
                    _error("nonnegative costs.round_trip_per_contract required")
                excludes = evidence["excludes"]
                if not isinstance(excludes, list) or len(excludes) > 32:
                    _error("costs.excludes must be a list of at most 32 strings")
                for excluded in excludes:
                    _text(excluded, "costs.excludes entry")
            clock = aware_time(evidence["as_of"])
            if clock > cutoff:
                problems.append("FUTURE_" + name.upper() + "_CLOCK")
            elif (cutoff - clock).total_seconds() > ttl:
                problems.append("STALE_" + name.upper())
        validation["usable"][name] = not problems
        validation["missing_data"].extend(problems)
        if relevant:
            validation["blockers"].extend("MISSING_" + issue if issue == name.upper() else issue for issue in problems)


MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
MAX_BARS = 2000


def _bounded_json(value):
    """Bound before serialization/copy: depth, nodes, containers and strings."""
    import json
    import math

    active = set()
    count = 0

    def visit(item, depth):
        nonlocal count
        count += 1
        if depth > 8 or count > 30000:
            _error("snapshot nesting/node limit exceeded")
        if type(item) in (dict, list):
            marker = id(item)
            if marker in active:
                _error("cyclic snapshot is not JSON")
            if len(item) > (32 if type(item) is dict else MAX_BARS):
                _error("snapshot container count limit exceeded")
            active.add(marker)
            if type(item) is dict:
                for key, child in item.items():
                    if not isinstance(key, str) or len(key) > 64:
                        _error("JSON object keys must be bounded strings")
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
            active.remove(marker)
        elif type(item) is str:
            if len(item) > 2048:
                _error("snapshot string length limit exceeded")
        elif type(item) is int:
            if abs(item) > 10**30:
                _error("snapshot integer magnitude limit exceeded")
        elif type(item) is float:
            if not math.isfinite(item):
                _error("nonfinite JSON number")
        elif item is not None and type(item) is not bool:
            _error("snapshot must contain JSON types only")

    visit(value, 0)
    size = 0
    for chunk in json.JSONEncoder(allow_nan=False, separators=(",", ":")).iterencode(value):
        size += len(chunk.encode("utf-8"))
        if size > MAX_SNAPSHOT_BYTES:
            _error("snapshot exceeds 16 MiB serialized JSON")
