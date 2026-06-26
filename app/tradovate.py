"""Tradovate API client - real futures data (NQ, ES, GC).

Auth flow: POST /auth/accesstokenrequest -> accessToken (valid ~80 min).
We cache the token and reuse it. Falls back to raising DataError if no creds.

Endpoints:
  demo:  https://demo.tradovateapi.com/v1
  live:  https://live.tradovateapi.com/v1
Market data (md) uses a separate host:
  https://md.tradovateapi.com/v1
"""
import time

import requests

from app.config import settings

DEMO_BASE = "https://demo.tradovateapi.com/v1"
LIVE_BASE = "https://live.tradovateapi.com/v1"
MD_BASE = "https://md.tradovateapi.com/v1"


class DataError(Exception):
    pass


_token_cache: dict = {"token": None, "exp": 0.0}


def _base() -> str:
    return DEMO_BASE if settings.tradovate_demo else LIVE_BASE


def configured() -> bool:
    return bool(settings.tradovate_username and settings.tradovate_password
                and settings.tradovate_cid and settings.tradovate_sec)


def get_access_token() -> str:
    """Authenticate and cache the access token."""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["exp"] - 60:
        return _token_cache["token"]
    if not configured():
        raise DataError("Tradovate credentials not configured")
    payload = {
        "name": settings.tradovate_username,
        "password": settings.tradovate_password,
        "appId": settings.tradovate_app_id,
        "appVersion": settings.tradovate_app_version,
        "cid": settings.tradovate_cid,
        "sec": settings.tradovate_sec,
    }
    r = requests.post(f"{_base()}/auth/accesstokenrequest", json=payload, timeout=15)
    r.raise_for_status()
    d = r.json()
    tok = d.get("accessToken")
    if not tok:
        raise DataError(f"Tradovate auth failed: {str(d)[:160]}")
    # expirationTime is ISO; default ~80 min, cache 75.
    _token_cache["token"] = tok
    _token_cache["exp"] = now + 75 * 60
    return tok


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {get_access_token()}"}


def find_contract(symbol: str) -> dict:
    """Resolve the front-month contract for a root symbol (e.g. 'NQ')."""
    r = requests.get(f"{_base()}/contract/find", params={"name": symbol},
                     headers=_auth_headers(), timeout=15)
    r.raise_for_status()
    d = r.json()
    if not d or "id" not in d:
        raise DataError(f"contract not found for {symbol}: {str(d)[:120]}")
    return d


def fetch_quote(symbol: str) -> dict:
    """Latest price for a futures root symbol via Tradovate market data."""
    contract = find_contract(symbol)
    cid = contract["id"]
    r = requests.get(f"{MD_BASE}/quote/get", params={"contractId": cid},
                     headers=_auth_headers(), timeout=15)
    r.raise_for_status()
    d = r.json()
    entries = d.get("entries", {}) if isinstance(d, dict) else {}
    last = (entries.get("Trade") or {}).get("price")
    if last is None:
        raise DataError(f"no quote for {symbol}: {str(d)[:120]}")
    return {"price": float(last), "contract": contract.get("name", symbol)}


def fetch_history(symbol: str, bars: int = 60) -> dict:
    """Daily OHLC history for a futures root symbol via getChart.

    Returns {"closes":[...], "highs":[...], "lows":[...]} oldest..newest.
    """
    contract = find_contract(symbol)
    cid = contract["id"]
    body = {
        "symbol": cid,
        "chartDescription": {"underlyingType": "DailyBar", "elementSize": 1,
                             "elementSizeUnit": "UnderlyingUnits"},
        "timeRange": {"asMuchAsElements": bars},
    }
    r = requests.post(f"{MD_BASE}/getChart", json=body, headers=_auth_headers(), timeout=20)
    r.raise_for_status()
    d = r.json()
    bars_data = []
    if isinstance(d, dict):
        for pkt in d.get("charts", d.get("bars", [])):
            bars_data.append(pkt)
    if not bars_data:
        raise DataError(f"no history for {symbol}: {str(d)[:160]}")
    closes = [float(b["close"]) for b in bars_data if "close" in b]
    highs = [float(b["high"]) for b in bars_data if "high" in b]
    lows = [float(b["low"]) for b in bars_data if "low" in b]
    if len(closes) < 2:
        raise DataError(f"insufficient history for {symbol}")
    return {"closes": closes, "highs": highs, "lows": lows,
            "contract": contract.get("name", symbol)}
