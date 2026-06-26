"""Real data fetchers for TwelveData (prices) and FRED (macro)."""
import requests

from app.config import settings

TD_BASE = "https://api.twelvedata.com"
FRED_BASE = "https://api.stlouisfed.org/fred"


class DataError(Exception):
    """Raised when a data source cannot return usable data."""


def fetch_td_quote(symbol: str) -> dict:
    """Latest quote for a symbol from TwelveData."""
    key = settings.twelvedata_api_key
    if not key:
        raise DataError("no TwelveData key configured")
    r = requests.get(
        f"{TD_BASE}/quote", params={"symbol": symbol, "apikey": key}, timeout=10
    )
    r.raise_for_status()
    d = r.json()
    if isinstance(d, dict) and d.get("status") == "error":
        raise DataError(d.get("message", "TwelveData error"))
    if "close" not in d:
        raise DataError(f"unexpected TwelveData response: {str(d)[:120]}")
    return {
        "price": float(d["close"]),
        "prev": float(d.get("previous_close", d["close"])),
        "change_pct": float(d.get("percent_change", 0.0)),
    }


def fetch_fred_latest(series_id: str) -> dict:
    """Latest two observations for a FRED series."""
    key = settings.fred_api_key
    if not key:
        raise DataError("no FRED key configured")
    r = requests.get(
        f"{FRED_BASE}/series/observations",
        params={
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 2,
        },
        timeout=10,
    )
    r.raise_for_status()
    d = r.json()
    obs = [o for o in d.get("observations", []) if o.get("value") not in (".", "")]
    if not obs:
        raise DataError(f"no observations for {series_id}")
    latest = float(obs[0]["value"])
    prev = float(obs[1]["value"]) if len(obs) > 1 else latest
    return {"latest": latest, "prev": prev, "date": obs[0]["date"]}
