"""Step 4 — /bias endpoint (real data) + persists each result as history."""
import json

from fastapi import APIRouter

from app.database import SessionLocal
from app.datasources import DataError, fetch_fred_latest, fetch_td_quote
from app.models import BiasSnapshot
from app.schemas import BiasResponse, InstrumentBias

router = APIRouter()

PROXY = {"NQ": "QQQ", "ES": "SPY", "GOLD": "GLD"}
THRESH = 0.1
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


def _save_snapshot(resp: BiasResponse) -> None:
    """Persist the computed bias for later backtesting. Best-effort."""
    try:
        db = SessionLocal()
        snap = BiasSnapshot(
            data_ready=resp.data_ready, regime=resp.regime,
            nq_bias=resp.NQ.bias, nq_price=resp.NQ.price, nq_change_pct=resp.NQ.change_pct,
            es_bias=resp.ES.bias, es_price=resp.ES.price, es_change_pct=resp.ES.change_pct,
            gold_bias=resp.GOLD.bias, gold_price=resp.GOLD.price, gold_change_pct=resp.GOLD.change_pct,
            payload=json.dumps(resp.model_dump()),
        )
        db.add(snap)
        db.commit()
    except Exception:
        pass
    finally:
        try:
            db.close()
        except Exception:
            pass


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
            ff = fetch_fred_latest(sid)
            macro[label] = {
                "latest": ff["latest"], "prev": ff["prev"], "date": ff["date"],
                "change": round(ff["latest"] - ff["prev"], 4),
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
    resp = BiasResponse(
        data_ready=td_ok, regime=regime, explanation=explanation,
        sources=sources, macro=macro, **instruments,
    )
    _save_snapshot(resp)
    return resp
