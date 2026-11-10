"""CONSPICUOUSLY SYNTHETIC offline cases, NOT quotes or real specifications.

Every invocation builds fresh bars and evidence. These invented TEST instruments,
prices, rates, costs and margins establish no financial performance or data rights.
"""

from copy import deepcopy
from datetime import date, timedelta


AS_OF = "2026-11-10T08:00:00Z"
SYNTHETIC = "SYNTHETIC_FIXTURE_NOT_LIVE"


def snapshot(kind="future", **overrides):
    """Build a fresh fake future/option; recursively merge object overrides.

    Lists and scalars replace their target. Overridden objects are deep-copied,
    so modifying a returned case never modifies another case or the caller.
    """
    if kind not in ("future", "option"):
        raise ValueError("synthetic kind must be future or option")
    dates = []
    day = date(2026, 11, 9)
    while len(dates) < 200:
        if day.weekday() < 5:
            dates.append(day.isoformat())
        day -= timedelta(days=1)
    dates.reverse()
    bars = []
    for index, day in enumerate(dates):
        close = (index + 201) / 4
        bars.append({"date": day, "open": close, "high": close + 1,
                     "low": close - 1, "close": close, "volume": 0, "source": SYNTHETIC})
    contract_id = "TEST:CALL" if kind == "option" else "TEST:FUTURE"
    contract = {
        "contract_id": contract_id, "venue": "TEST", "root": "INDEX",
        "family": "index_option" if kind == "option" else "index_future",
        "underlying_id": "TEST:INDEX", "currency": "USD", "value_per_price_unit": "5",
        "tick_size": "0.25", "last_trade_at": "2026-12-18T14:30:00Z",
        "expiry_at": "2026-12-18T14:30:00Z", "settlement": "cash",
        "spec_source": SYNTHETIC, "spec_effective_at": "2026-01-01T00:00:00Z",
        "standard_deliverable": True,
    }
    if kind == "option":
        contract.update(right="call", strike="100", exercise="european", underlying_kind="cash_index")
    result = {
        "schema_version": 1, "contract": contract,
        "quote": {
            "contract_id": contract_id, "bid": "5.75" if kind == "option" else "100",
            "ask": "6" if kind == "option" else "100.25", "bid_contracts": 10, "ask_contracts": 10,
            "observed_at": "2026-11-10T07:59:59Z", "received_at": "2026-11-10T07:59:59Z",
            "delay_seconds": 0, "market_state": "open",
        },
        "underlying": {
            "underlying_id": "TEST:INDEX", "currency": "USD", "spot": "100",
            "spot_observed_at": "2026-11-10T07:59:59Z", "interval": "1d",
            "price_basis": "price_index", "adjustment": "raw", "source": SYNTHETIC,
            "retrieved_at": AS_OF, "bars": bars,
            "last_bar_finalized_at": dates[-1] + "T21:00:00Z",
        },
        "source": {
            "provider": SYNTHETIC, "retrieved_at": AS_OF, "data_mode": "fixture",
            "entitlement": "unverified", "historical_vintage": "SYNTHETIC generated rows; no archival claim",
        },
        "rates": {
            "risk_free": "0.04", "dividend_yield": "0.01", "as_of": AS_OF, "source": SYNTHETIC,
            "currency": "USD", "underlying_id": "TEST:INDEX", "compounding": "continuous", "day_count": "ACT/365F",
        },
        "margin": {
            "amount_per_contract": "50", "currency": "USD", "contract_id": contract_id,
            "as_of": AS_OF, "source": SYNTHETIC, "scope": "exchange_reference", "account_specific": False,
        },
        "costs": {
            "round_trip_per_contract": "1", "currency": "USD", "contract_id": contract_id,
            "as_of": AS_OF, "source": SYNTHETIC, "excludes": ["SYNTHETIC taxes and slippage excluded"],
        },
    }

    def merge(target, changes):
        for key, value in changes.items():
            if isinstance(target.get(key), dict) and isinstance(value, dict):
                merge(target[key], value)
            else:
                target[key] = deepcopy(value)
    merge(result, overrides)
    return result
