"""Universe ranking guards must run before analysis or any network work."""
import pytest


def test_rank_refuses_implicit_or_empty_universe():
    from tradeguard.ranking import rank_snapshots
    with pytest.raises(ValueError, match="1..50"):
        rank_snapshots([])


def test_rank_refuses_cross_asset_scales():
    from tradeguard.ranking import rank_snapshots
    with pytest.raises(ValueError, match="instrument family"):
        rank_snapshots([{"symbol": "A", "asset_type": "stock", "currency": "USD"}, {"symbol": "B", "asset_type": "etf", "currency": "USD"}])
