import numpy as np

from scanner.config import Config
from scanner.data import chunk_symbols, parse_bars, quality_filter
from scanner.universe import filter_assets
from tests.fixtures import make_bars


def test_chunk_symbols():
    syms = [f"S{i}" for i in range(45)]
    chunks = chunk_symbols(syms, size=20)
    assert [len(c) for c in chunks] == [20, 20, 5]
    assert [s for c in chunks for s in c] == syms


def test_parse_bars_multiple_pages():
    pages = [
        {"bars": {"AAA": [
            {"t": "2026-07-09T04:00:00Z", "o": 10, "h": 11, "l": 9.5, "c": 10.5, "v": 1000},
        ], "BBB": [
            {"t": "2026-07-09T04:00:00Z", "o": 5, "h": 5.2, "l": 4.9, "c": 5.1, "v": 2000},
        ]}},
        {"bars": {"AAA": [
            {"t": "2026-07-10T04:00:00Z", "o": 10.5, "h": 12, "l": 10.4, "c": 11.8, "v": 1500},
        ]}},
    ]
    result = parse_bars(pages)
    assert set(result) == {"AAA", "BBB"}
    aaa = result["AAA"]
    assert list(aaa.columns) == ["open", "high", "low", "close", "volume"]
    assert len(aaa) == 2
    assert aaa["close"].iloc[-1] == 11.8
    assert aaa.index.is_monotonic_increasing


def test_parse_bars_empty():
    assert parse_bars([{"bars": {}}]) == {}


def test_quality_filter():
    cfg = Config()  # min price 1 (user wants everything from $1), min avg volume 300k
    bars = {
        "GOOD": make_bars(np.full(300, 25.0), volumes=np.full(300, 500_000.0)),
        "CHEAP": make_bars(np.full(300, 2.0), volumes=np.full(300, 500_000.0)),
        "PENNY": make_bars(np.full(300, 0.40), volumes=np.full(300, 500_000.0)),
        "THIN": make_bars(np.full(300, 25.0), volumes=np.full(300, 100_000.0)),
    }
    assert quality_filter(bars, cfg) == ["CHEAP", "GOOD"]


def test_filter_assets_excludes_junk():
    assets = [
        {"symbol": "AAPL", "name": "Apple Inc. Common Stock", "tradable": True,
         "exchange": "NASDAQ", "status": "active"},
        {"symbol": "FOO.W", "name": "Foo Warrant", "tradable": True,
         "exchange": "NYSE", "status": "active"},
        {"symbol": "BARW", "name": "Bar Corp Warrants", "tradable": True,
         "exchange": "NASDAQ", "status": "active"},
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "tradable": True,
         "exchange": "ARCA", "status": "active"},
        {"symbol": "DEAD", "name": "Dead Co", "tradable": False,
         "exchange": "NYSE", "status": "active"},
        {"symbol": "ACQU", "name": "Blank Check Acquisition Corp", "tradable": True,
         "exchange": "NASDAQ", "status": "active"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "tradable": True,
         "exchange": "NASDAQ", "status": "active"},
    ]
    kept = filter_assets(assets)
    assert {a["symbol"] for a in kept} == {"AAPL", "MSFT"}
