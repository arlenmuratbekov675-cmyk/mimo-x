"""Step 3 — /bias endpoint backed by real TwelveData + FRED data.

Transparent v0 logic:
- Price bias = sign of daily percent change (threshold +/- 0.1%). No fake confidence.
- Futures NQ/ES/GOLD use liquid ETF proxies (QQQ/SPY/GLD) on TwelveData free tier;
  the proxy used is reported in 'proxy_symbol'.
- Macro from FRED: US 10Y yield (DGS10) and VIX (VIXCLS).
- Each source reports its own status; a failure in one does not hide the others.
- No trade execution.
"""
from fastapi import APIRouter

from app.datasources import DataError, fetch_fred_latest, fetch_td_quote
from app.schemas import BiasResponse, InstrumentBias

router = APIRouter()

PROXY = {"NQ": "QQQ", "ES": "SPY", "GOLD": "GLD"}
THRESH = 0.1  # percent move treated as directional
FRED_SERIES = {"US10Y": "DGS10", "VIX": "VIXCLS"}


def classify(change_pct: float) -> str:
    if change_pct > THRESH:
        return "LONG"
    if change_pct < -THRESH:
        return "SHORT"
    return "NEUTRAL"


def compute_regime(instruments: dict, macro: dict):
    nq, es = instruments["NQ"].bias, instruments["ES"].bias
    if nq == "DATA_NOT_READY" or es == "DATA_NOT_READY":
        return "DATA_NOT_READY", "Equity price data unavailable; regime cannot be computed."
    vix = macro.get("VIX", {})
    vix_change = vix.get("change") if "error" not in vix else None
    long_eq = nq == "LONG" and es == "LONG"
    short_eq = nq == "SHORT" and es == "SHORT"
    vix_note = f" VIX change {vix_change:+.2f}." if isinstance(vix_change, (int, float)) else ""
    if long_eq and (vix_change is None or vix_change < 0):
        return "RISK_ON", f"NQ and ES both LONG.{vix_note}"
    if short_eq and (vix_change is None or vix_change > 0):
        return "RISK_OFF", f"NQ and ES both SHORT.{vix_note}"
    return "MIXED", f"Equity/volatility signals mixed (NQ={nq}, ES={es}).{vix_note}"


@router.get("/bias", response_model=BiasResponse)
def get_bias() -> BiasResponse:
    sources = {}
    instruments = {}
    td_ok = True
    for sym, proxy in PROXY.items():
        try:
            q = fetch_td_quote(proxy)
            b = classify(q["change_pct"])
            instruments[sym] = InstrumentBias(
                symbol=sym, bias=b, confidence=None,
                price=q["price"], change_pct=q["change_pct"], proxy_symbol=proxy,
                explanation=(
                    f"{sym} via {proxy}: last {q['price']} "
                    f"({q['change_pct']:+.2f}% vs prev close). "
                    f"Bias {b} from sign of daily change (threshold +/-{THRESH}%)."
                ),
            )
        except (DataError, Exception) as e:
            td_ok = False
            instruments[sym] = InstrumentBias(
                symbol=sym, bias="DATA_NOT_READY", confidence=None, proxy_symbol=proxy,
                explanation=f"TwelveData fetch failed for {proxy}.", error=str(e),
            )
    sources["twelvedata"] = "ok" if td_ok else "error"

    macro = {}
    fred_ok = True
    for label, sid in FRED_SERIES.items():
        try:
            f = fetch_fred_latest(sid)
            macro[label] = {
                "latest": f["latest"], "prev": f["prev"], "date": f["date"],
                "change": round(f["latest"] - f["prev"], 4),
            }
        except (DataError, Exception) as e:
            fred_ok = False
            macro[label] = {"error": str(e)}
    sources["fred"] = "ok" if fred_ok else "error"

    regime, regime_expl = compute_regime(instruments, macro)
    explanation = (
        f"Regime {regime}. {regime_expl} "
        f"Sources: TwelveData={sources['twelvedata']}, FRED={sources['fred']}. "
        "Confidence intentionally omitted until a backtested model exists."
    )
    return BiasResponse(
        data_ready=td_ok, regime=regime, explanation=explanation,
        sources=sources, macro=macro, **instruments,
    )
