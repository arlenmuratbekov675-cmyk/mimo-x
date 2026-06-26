"""FastAPI router for the cTrader OAuth redirect."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.execution import oauth

router = APIRouter()

@router.get("/ctrader/callback", response_class=HTMLResponse)
def ctrader_callback(request: Request):
    code = request.query_params.get("code")
    err = request.query_params.get("error")
    if err:
        return f"<h2>cTrader auth error: {err}</h2>"
    if not code:
        return "<h2>No authorization code received.</h2>"
    try:
        oauth.exchange_code(code)
        return ("<h2>cTrader connected.</h2><p>Token stored. You can close this "
                "tab and return to MiMo.</p>")
    except Exception as e:
        return f"<h2>Token exchange failed: {e}</h2>"
