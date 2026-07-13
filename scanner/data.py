"""Alpaca market-data client: batched daily bars + universe quality filter.

Network calls live in fetch_daily_bars; everything else is pure and unit
tested. Free plan: IEX feed, 200 requests/minute.
"""
import os
import time

import pandas as pd
import requests

from .config import Config, DEFAULT

DATA_URL = "https://data.alpaca.markets/v2/stocks/bars"
BATCH_SIZE = 200  # symbols per request; a year of daily bars fits the 10k cap comfortably


def auth_headers():
    return {
        "APCA-API-KEY-ID": os.environ["ALPACA_KEY"],
        "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET"],
    }


def chunk_symbols(symbols, size=BATCH_SIZE):
    return [symbols[i:i + size] for i in range(0, len(symbols), size)]


def parse_bars(pages):
    """Merge paginated multi-symbol bar payloads into per-symbol DataFrames."""
    rows = {}
    for page in pages:
        for symbol, bars in (page.get("bars") or {}).items():
            rows.setdefault(symbol, []).extend(bars)
    result = {}
    for symbol, bars in rows.items():
        df = pd.DataFrame(bars)
        df.index = pd.to_datetime(df.pop("t"))
        df = df.rename(columns={"o": "open", "h": "high", "l": "low",
                                "c": "close", "v": "volume"})
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        result[symbol] = df.sort_index()
    return result


def quality_filter(bars_by_symbol, cfg: Config = DEFAULT):
    """Symbols liquid enough to bother scanning: min price and avg volume."""
    kept = []
    for symbol, bars in bars_by_symbol.items():
        if bars.empty:
            continue
        price = bars["close"].iloc[-1]
        avg_vol = bars["volume"].tail(cfg.avg_volume_days).mean()
        if price >= cfg.min_price and avg_vol >= cfg.min_avg_volume:
            kept.append(symbol)
    return sorted(kept)


def fetch_daily_bars(symbols, start, end, session=None, pause=0.35):
    """Fetch ~340 sessions of daily bars for every symbol, batched + paginated."""
    session = session or requests.Session()
    all_pages = []
    for batch in chunk_symbols(symbols):
        params = {
            "symbols": ",".join(batch),
            "timeframe": "1Day",
            "start": start,
            "end": end,
            "limit": 10000,
            "adjustment": "split",
            "feed": "iex",
        }
        while True:
            resp = session.get(DATA_URL, params=params, headers=auth_headers(), timeout=30)
            if resp.status_code == 429:
                time.sleep(10)
                continue
            resp.raise_for_status()
            page = resp.json()
            all_pages.append(page)
            token = page.get("next_page_token")
            if not token:
                break
            params["page_token"] = token
        time.sleep(pause)  # stay far under 200 req/min
    return parse_bars(all_pages)
