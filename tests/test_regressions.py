"""Independent final-review regression cases."""
import pytest
from datetime import date, timedelta


def test_weekly_rows_cannot_produce_daily_annualized_ml_statistics():
    from tradeguard.validation import walk_forward
    bars = [{"date": (date(2020, 1, 1) + timedelta(days=7*i)).isoformat(), "open": 100+i/10, "high": 102+i/10, "low": 98+i/10, "close": 101+i/10, "volume": 10000} for i in range(280)]
    with pytest.raises(ValueError, match="daily|gap|session"):
        walk_forward(bars, min_train=50, adjustment="split")


def test_microstructure_event_work_is_hard_bounded():
    from tradeguard.microstructure import order_flow_imbalance
    events = [{"timestamp": i, "bid": 100, "ask": 101, "bid_size": 2, "ask_size": 3} for i in range(10001)]
    with pytest.raises(ValueError, match="10000|10,000|maximum"):
        order_flow_imbalance(events)
