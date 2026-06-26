"""cTrader OAuth token exchange. KYC-gated - works once app is Active.

Flow:
  1. Build authorize URL (done in browser already).
  2. cTrader redirects to CTRADER_REDIRECT_URI with ?code=...
  3. exchange_code() trades that code for access + refresh tokens.
  4. refresh() renews when expired.
Tokens are persisted to a small json next to the DB (not committed).
"""
from __future__ import annotations
import json, os, time
import requests

TOKEN_URL = "https://openapi.ctrader.com/apps/token"
_STORE = os.getenv("CTRADER_TOKEN_FILE", "/code/data/ctrader_token.json")

def _creds():
    return os.getenv("CTRADER_CLIENT_ID"), os.getenv("CTRADER_SECRET"), os.getenv("CTRADER_REDIRECT_URI")

def _save(tok: dict):
    tok["_saved_at"] = time.time()
    os.makedirs(os.path.dirname(_STORE), exist_ok=True)
    with open(_STORE, "w") as f:
        json.dump(tok, f)

def load() -> dict | None:
    try:
        with open(_STORE) as f:
            return json.load(f)
    except Exception:
        return None

def exchange_code(code: str) -> dict:
    cid, secret, redirect = _creds()
    r = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": redirect, "client_id": cid, "client_secret": secret,
    }, timeout=15)
    r.raise_for_status()
    tok = r.json(); _save(tok); return tok

def refresh() -> dict | None:
    tok = load()
    if not tok or "refresh_token" not in tok:
        return None
    cid, secret, _ = _creds()
    r = requests.post(TOKEN_URL, data={
        "grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
        "client_id": cid, "client_secret": secret,
    }, timeout=15)
    r.raise_for_status()
    new = r.json(); _save(new); return new

def is_authorized() -> bool:
    return load() is not None
