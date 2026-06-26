"""Data fetchers for TwelveData (prices/series) and FRED (macro), with TTL cache."""
import time

import requests

from app.config import settings

TD_BASE = "https://api.twelvedata.com"
FRED_BASE = "https://api.stlouisfed.org/fred"


class DataError(Exception):
    """Raised when a data source cannot return usable data."""


# ---- tiny in-process TTL cache (resets on restart; fine for one container) ----
_CACHE: dict[str, tuple[float, object]] = {}


def _cache_get(key: str):
    item = _CACHE.get(key)
    if not item:
        return None
    ts, val = item
    if time.time() - ts > settings.cache_ttl_seconds:
        _CACHE.pop(key, None)
        return None
    return val


def _cache_set(key: str, val) -> None:
    _CACHE[key] = (time.time(), val)


def cache_info() -> dict:
    return {"entries": len(_CACHE), "ttl_seconds": settings.cache_ttl_seconds}


def fetch_td_quote(symbol: str) -> dict:
    """Latest quote for a symbol from TwelveData (cached)."""
    ck = f"td_quote:{symbol}"
    hit = _cache_get(ck)
    if hit is not None:
        return hit
    key = settings.twelvedata_api_key
    if not key:
        raise DataError("no TwelveData key configured")
    r = requests.get(f"{TD_BASE}/quote", params={"symbol": symbol, "apikey": key}, timeout=10)
    r.raise_for_status()
    d = r.json()
    if isinstance(d, dict) and d.get("status") == "error":
        raise DataError(d.get("message", "TwelveData error"))
    if "close" not in d:
        raise DataError(f"unexpected TwelveData response: {str(d)[:120]}")
    out = {
        "price": float(d["close"]),
        "prev": float(d.get("previous_close", d["close"])),
        "change_pct": float(d.get("percent_change", 0.0)),
    }
    _cache_set(ck, out)
    return out


def fetch_td_series(symbol: str, outputsize: int = 60, interval: str = "1day") -> list[float]:
    """Closing prices (oldest..newest) for a symbol from TwelveData (cached)."""
    ck = f"td_series:{symbol}:{interval}:{outputsize}"
    hit = _cache_get(ck)
    if hit is not None:
        return hit
    key = settings.twelvedata_api_key
    if not key:
        raise DataError("no TwelveData key configured")
    r = requests.get(
        f"{TD_BASE}/time_series",
        params={"symbol": symbol, "interval": interval, "outputsize": outputsize, "apikey": key},
        timeout=15,
    )
    r.raise_for_status()
    d = r.json()
    if isinstance(d, dict) and d.get("status") == "error":
        raise DataError(d.get("message", "TwelveData error"))
    values = d.get("values")
    if not values:
        raise DataError(f"no time_series for {symbol}: {str(d)[:120]}")
    # API returns newest-first; reverse to oldest..newest.
    closes = [float(v["close"]) for v in reversed(values) if v.get("close") not in (None, "")]
    if len(closes) < 2:
        raise DataError(f"insufficient series for {symbol}")
    _cache_set(ck, closes)
    return closes


def fetch_fred_latest(series_id: str) -> dict:
    """Latest two observations for a FRED series (cached)."""
    ck = f"fred:{series_id}"
    hit = _cache_get(ck)
    if hit is not None:
        return hit
    key = settings.fred_api_key
    if not key:
        raise DataError("no FRED key configured")
    r = requests.get(
        f"{FRED_BASE}/series/observations",
        params={"series_id": series_id, "api_key": key, "file_type": "json",
                "sort_order": "desc", "limit": 2},
        timeout=10,
    )
    r.raise_for_status()
    d = r.json()
    obs = [o for o in d.get("observations", []) if o.get("value") not in (".", "")]
    if not obs:
        raise DataError(f"no observations for {series_id}")
    latest = float(obs[0]["value"])
    prev = float(obs[1]["value"]) if len(obs) > 1 else latest
    out = {"latest": latest, "prev": prev, "date": obs[0]["date"]}
    _cache_set(ck, out)
    return out
