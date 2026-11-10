"""Frozen pre-extraction equity outputs; synthetic inputs prove no edge."""

from copy import deepcopy

import pytest


def _cash_bars(count, pattern="rising", adjustment="raw"):
    """Deterministic synthetic cash OHLCV, never derivative candles."""
    bars = []
    for i in range(count):
        close = (i + 1 if pattern == "rising" else
                 400 - i if pattern == "falling" else
                 100 if pattern == "flat" else 100 + (i % 5) * 3 - i % 3)
        scale = 2 if adjustment != "raw" else 1
        bar = {"open": close * scale, "high": (close + 1) * scale,
               "low": max(.5, close - 1) * scale,
               "close": close * scale, "volume": 0}
        if adjustment != "raw":
            bar["adjusted_close"] = close
        bars.append(bar)
    return bars


# Captured from equity._technical before extraction, not from the new aliases.
GOLDEN_CASES = [{'case': [1, 'rising', 'raw'],
  'metrics': {'sma20': None,
              'sma50': None,
              'sma200': None,
              'ema12': None,
              'ema26': None,
              'macd': None,
              'rsi14': None,
              'atr14': None,
              'vol20': None,
              'max_drawdown': 0.0,
              'return21': None,
              'return63': None,
              'return252': None,
              'momentum12_1': None,
              'dollar_volume20': None},
  'warnings': ['existing caller caveat']},
 {'case': [200, 'rising', 'raw'],
  'metrics': {'sma20': 190.5,
              'sma50': 175.5,
              'sma200': 100.5,
              'ema12': 194.5,
              'ema26': 187.5,
              'macd': 7.0,
              'rsi14': 100,
              'atr14': 2.0,
              'vol20': 0.0026205835145621885,
              'max_drawdown': 0.0,
              'return21': 0.11731843575418988,
              'return63': 0.45985401459854014,
              'return252': None,
              'momentum12_1': None,
              'dollar_volume20': 0},
  'warnings': ['existing caller caveat']},
 {'case': [17, 'zigzag', 'raw'],
  'metrics': {'sma20': None,
              'sma50': None,
              'sma200': None,
              'ema12': 104.47148411093126,
              'ema26': None,
              'macd': None,
              'rsi14': 51.03230890464934,
              'atr14': 5.624635568513119,
              'vol20': None,
              'max_drawdown': -0.11711711711711714,
              'return21': None,
              'return63': None,
              'return252': None,
              'momentum12_1': None,
              'dollar_volume20': None},
  'warnings': ['existing caller caveat']},
 {'case': [260, 'rising', 'split'],
  'metrics': {'sma20': 250.5,
              'sma50': 235.5,
              'sma200': 160.5,
              'ema12': 254.5,
              'ema26': 247.5,
              'macd': 7.0,
              'rsi14': 100,
              'atr14': 2.0,
              'vol20': 0.0015104341749975101,
              'max_drawdown': 0.0,
              'return21': 0.08786610878661083,
              'return63': 0.31979695431472077,
              'return252': 31.5,
              'momentum12_1': 28.875,
              'dollar_volume20': 0},
  'warnings': ['existing caller caveat']},
 {'case': [260, 'rising', 'total_return'],
  'metrics': {'sma20': 250.5,
              'sma50': 235.5,
              'sma200': 160.5,
              'ema12': 254.5,
              'ema26': 247.5,
              'macd': 7.0,
              'rsi14': 100,
              'atr14': None,
              'vol20': 0.0015104341749975101,
              'max_drawdown': 0.0,
              'return21': 0.08786610878661083,
              'return63': 0.31979695431472077,
              'return252': 31.5,
              'momentum12_1': 28.875,
              'dollar_volume20': 0},
  'warnings': ['existing caller caveat',
               'ATR unavailable: total-return adjusted close differs from OHLC basis']},
 {'case': [260, 'flat', 'raw'],
  'metrics': {'sma20': 100,
              'sma50': 100,
              'sma200': 100,
              'ema12': 100.0,
              'ema26': 100.0,
              'macd': 0.0,
              'rsi14': 50,
              'atr14': 2.0,
              'vol20': 0.0,
              'max_drawdown': 0.0,
              'return21': 0.0,
              'return63': 0.0,
              'return252': 0.0,
              'momentum12_1': 0.0,
              'dollar_volume20': 0},
  'warnings': ['existing caller caveat']},
 {'case': [260, 'falling', 'raw'],
  'metrics': {'sma20': 150.5,
              'sma50': 165.5,
              'sma200': 240.5,
              'ema12': 146.5,
              'ema26': 153.5,
              'macd': -7.0,
              'rsi14': 0.0,
              'atr14': 2.0,
              'vol20': 0.004104782660874491,
              'max_drawdown': -0.6475,
              'return21': -0.12962962962962965,
              'return63': -0.3088235294117647,
              'return252': -0.6412213740458015,
              'momentum12_1': -0.5877862595419847,
              'dollar_volume20': 0},
  'warnings': ['existing caller caveat']}]


@pytest.mark.parametrize("golden", GOLDEN_CASES,
                         ids=["one-bar", "200-rising", "wilder-zigzag", "split",
                              "total-return-warning", "flat", "falling"])
def test_shared_technical_matches_frozen_equity_metrics_and_warnings(golden):
    from tradeguard import equity
    from tradeguard.indicators import technical

    count, pattern, adjustment = golden["case"]
    bars = _cash_bars(count, pattern, adjustment)
    before = deepcopy(bars)
    shared_warnings = ["existing caller caveat"]
    equity_warnings = list(shared_warnings)
    actual = technical(bars, adjustment, shared_warnings)
    assert actual == golden["metrics"]
    assert actual == equity._technical(bars, adjustment, equity_warnings)
    assert shared_warnings == equity_warnings == golden["warnings"]
    assert bars == before


def test_equity_keeps_direct_legacy_import_aliases():
    from tradeguard import equity
    from tradeguard.indicators import ema, technical, wilder

    assert equity._ema is ema
    assert equity._wilder is wilder
    assert equity._technical is technical
    assert equity._coverage({"present": 0, "missing": None}) == {
        "available": 1, "total": 2, "fraction": .5, "status": "partial"}


@pytest.mark.parametrize("count", [1, 14, 15, 19, 20, 21, 22, 25, 26, 49, 50,
                                   199, 200, 252, 253])
def test_cash_indicator_observation_windows_stay_unchanged(count):
    from tradeguard.indicators import technical

    metrics = technical(_cash_bars(count), "raw", [])
    for period in (20, 50, 200):
        assert (metrics[f"sma{period}"] is not None) == (count >= period)
    for period in (12, 26):
        assert (metrics[f"ema{period}"] is not None) == (count >= period)
    assert (metrics["macd"] is not None) == (count >= 26)
    assert (metrics["rsi14"] is not None) == (count >= 15)
    assert (metrics["atr14"] is not None) == (count >= 15)
    assert (metrics["vol20"] is not None) == (count >= 21)
    for period in (21, 63, 252):
        assert (metrics[f"return{period}"] is not None) == (count > period)
    assert (metrics["momentum12_1"] is not None) == (count >= 253)
    assert (metrics["dollar_volume20"] is not None) == (count >= 20)


def test_shared_smoothers_keep_sma_seeds_and_original_recursion():
    from tradeguard.indicators import ema, wilder

    assert ema([2, 4], 3) is None
    assert ema([2, 4, 6], 3) == 4
    assert ema([2, 4, 6, 8, 10], 3) == 8
    assert wilder([2, 4], 3) is None
    assert wilder([2, 4, 6], 3) == 4
    assert wilder([2, 4, 6, 10], 3) == 6
    assert wilder([14] * 14) == 14
