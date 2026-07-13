"""US common-stock universe from Alpaca's assets endpoint.

The name/symbol heuristics drop non-stocks (warrants, rights, units, ETFs,
SPAC shells). Anything that slips through still has to survive the price,
volume, and history requirements downstream.
"""
import os

import requests

ASSETS_URL = "https://paper-api.alpaca.markets/v2/assets"
EXCHANGES = {"NYSE", "NASDAQ", "AMEX", "ARCA", "BATS"}
NAME_DENYLIST = (
    "warrant", " right", "rights", " unit", "units", "etf", "etn",
    " fund", "trust", "acquisition corp", "acquisition co",
)
SYMBOL_JUNK_CHARS = (".", "/", "-")


def _looks_like_common_stock(asset):
    if not asset.get("tradable"):
        return False
    if asset.get("exchange") not in EXCHANGES:
        return False
    symbol = asset["symbol"]
    if any(ch in symbol for ch in SYMBOL_JUNK_CHARS):
        return False
    name = (asset.get("name") or "").lower()
    if any(term in name for term in NAME_DENYLIST):
        return False
    # NASDAQ 5-letter suffixes: W=warrant, R=right, U=unit
    if len(symbol) == 5 and symbol[-1] in "WRU":
        return False
    return True


def filter_assets(assets):
    return [a for a in assets if _looks_like_common_stock(a)]


def fetch_assets(session=None):
    session = session or requests.Session()
    resp = session.get(
        ASSETS_URL,
        params={"status": "active", "asset_class": "us_equity"},
        headers={
            "APCA-API-KEY-ID": os.environ["ALPACA_KEY"],
            "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET"],
        },
        timeout=60,
    )
    resp.raise_for_status()
    return filter_assets(resp.json())
