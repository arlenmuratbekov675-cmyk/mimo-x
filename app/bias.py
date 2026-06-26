"""/bias endpoint - multi-factor engine (trend, breadth, volatility, macro)."""
import json

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.auth import require_api_key
from app.database import SessionLocal
from app.datasources import fetch_fred_latest, fetch_td_ohlc, fetch_td_series
from app import tradovate
from app import calendar as econ_calendar
from app.models import BiasSnapshot, Calibration
from app.schemas import BiasResponse, InstrumentBias
from app import signals

router = APIRouter()

PROXY = {"NQ": "QQQ", "ES": "SPY", "GOLD": "GLD"}
FUTURES = {"NQ": "NQ", "ES": "ES", "GOLD": "GC"}  # Tradovate root symbols


def _use_tradovate() -> bool:
    from app.config import settings
    if settings.price_feed == "proxy":
        return False
    if settings.price_feed == "tradovate":
        return True
    return tradovate.configured()  # auto


def get_instrument_ohlc(sym: str):
    """Return (ohlc_dict, source_label, instrument_name). Prefers real futures."""
    if _use_tradovate():
        try:
            root = FUTURES[sym]
            hist = tradovate.fetch_history(root, bars=60)
            return hist, "tradovate", hist.get("contract", root)
        except Exception:
            pass  # fall back to proxy below
    ohlc = fetch_td_ohlc(PROXY[sym], outputsize=60)
    return ohlc, "proxy", PROXY[sym]
# Sector ETFs for market breadth (equity participation).
BREADTH_BASKET = ["XLK", "XLF", "XLV", "XLI"]
FRED_SERIES = {"US10Y": "DGS10", "VIX": "VIXCLS", "DXY": "DTWEXBGS"}


def _load_calibration() -> dict:
    out = {}
    try:
        db = SessionLocal()
        for c in db.execute(select(Calibration)).scalars().all():
            out[c.instrument] = {"hit_rate": c.hit_rate, "samples": c.samples,
                                 "horizon_hours": c.horizon_hours}
        db.close()
    except Exception:
        pass
    return out


def _confidence_for(instr: str, raw: float, calib: dict) -> float | None:
    """Real confidence ONLY if a calibrated hit-rate with enough samples exists."""
    c = calib.get(instr)
    if not c or c.get("hit_rate") is None:
        return None
    from app.config import settings
    if c.get("samples", 0) < settings.backtest_min_samples:
        return None
    # Scale measured hit-rate by conviction (|raw|, capped at 1).
    conviction = min(1.0, abs(raw))
    base = 50.0  # a coin flip
    edge = (c["hit_rate"] * 100.0) - base
    return round(base + edge * conviction, 1)


def _save_snapshot(resp: BiasResponse) -> None:
    try:
        db = SessionLocal()
        db.add(BiasSnapshot(
            data_ready=resp.data_ready, regime=resp.regime,
            nq_bias=resp.NQ.bias, nq_price=resp.NQ.price,
            nq_change_pct=resp.NQ.change_pct, nq_raw=resp.NQ.raw_score,
            es_bias=resp.ES.bias, es_price=resp.ES.price,
            es_change_pct=resp.ES.change_pct, es_raw=resp.ES.raw_score,
            gold_bias=resp.GOLD.bias, gold_price=resp.GOLD.price,
            gold_change_pct=resp.GOLD.change_pct, gold_raw=resp.GOLD.raw_score,
            payload=json.dumps(resp.model_dump()),
        ))
        db.commit(); db.close()
    except Exception:
        pass


@router.get("/bias", response_model=BiasResponse, dependencies=[Depends(require_api_key)])
def get_bias() -> BiasResponse:
    sources = {}

    # --- macro (FRED) ---
    macro = {}
    fred_ok = True
    for label, sid in FRED_SERIES.items():
        try:
            ff = fetch_fred_latest(sid)
            macro[label] = {"latest": ff["latest"], "prev": ff["prev"],
                            "date": ff["date"], "change": round(ff["latest"] - ff["prev"], 4)}
        except Exception as e:
            fred_ok = False
            macro[label] = {"error": str(e)}
    sources["fred"] = "ok" if fred_ok else "error"
    macro_eq, macro_gold, macro_detail = signals.macro_score(macro)

    # --- breadth (sector ETFs) ---
    basket_closes = {}
    breadth_ok = True
    for sym in BREADTH_BASKET:
        try:
            basket_closes[sym] = fetch_td_series(sym, outputsize=60)
        except Exception:
            breadth_ok = False
    b_score, breadth_detail = signals.breadth_score(basket_closes)
    sources["breadth"] = "ok" if (breadth_ok and basket_closes) else "partial" if basket_closes else "error"

    # --- per-instrument ---
    calib = _load_calibration()
    instruments = {}
    td_ok = True
    for sym, proxy in PROXY.items():
        try:
            ohlc, feed_src, instr_name = get_instrument_ohlc(sym)
            series = ohlc["closes"]
            price = series[-1]
            change_pct = round((series[-1] / series[-2] - 1.0) * 100.0, 4)
            t_score, t_detail = signals.trend_score(series)
            vol, vol_detail = signals.volatility(series)
            atr_value = signals.atr(ohlc["highs"], ohlc["lows"], series)
            if sym == "GOLD":
                raw = signals.aggregate_gold(t_score, macro_gold)
                factors = {"trend": t_detail, "macro": {"gold_score": macro_gold},
                           "weights": signals.GOLD_WEIGHTS}
            else:
                raw = signals.aggregate_equity(t_score, b_score, macro_eq)
                factors = {"trend": t_detail,
                           "breadth": {"score": round(b_score, 3), **breadth_detail},
                           "macro": {"equity_score": macro_eq, **macro_detail},
                           "weights": signals.EQUITY_WEIGHTS}
            bias = signals.classify(raw)
            conf = _confidence_for(sym, raw, calib)
            plan = signals.trade_plan(bias, price, atr_value)
            squality = signals.signal_quality(raw, factors)
            instruments[sym] = InstrumentBias(
                symbol=sym, bias=bias, confidence=conf,
                price=price, change_pct=change_pct,
                raw_score=raw, atr=round(atr_value, 4) if atr_value else None,
                atr_pct=round(atr_value / price * 100, 3) if atr_value else None,
                trade_plan=plan, signal_quality=squality,
                proxy_symbol=instr_name, factors=factors,
                volatility=vol_detail,
                explanation=(
                    f"{sym} via {proxy}: raw_score={raw:+.3f} -> {bias}. "
                    f"Trend={t_score:+.2f}"
                    + (f", breadth={b_score:+.2f}" if sym != 'GOLD' else "")
                    + f", macro={(macro_gold if sym=='GOLD' else macro_eq):+.2f}. "
                    f"Volatility {vol_detail['regime']} ({vol_detail['daily_pct']}%/day). "
                    + ("Confidence from measured backtest." if conf is not None
                       else "Confidence null until backtest has enough samples.")
                ),
            )
        except Exception as e:
            td_ok = False
            instruments[sym] = InstrumentBias(
                symbol=sym, bias="DATA_NOT_READY", confidence=None,
                proxy_symbol=proxy,
                explanation=f"Data fetch failed for {proxy}.", error=str(e))
    sources["twelvedata"] = "ok" if td_ok else "error"
    sources["price_feed"] = "tradovate" if _use_tradovate() else "proxy"

    # --- regime ---
    nq, es = instruments["NQ"].bias, instruments["ES"].bias
    if nq == "DATA_NOT_READY" or es == "DATA_NOT_READY":
        regime = "DATA_NOT_READY"
    elif nq == "LONG" and es == "LONG":
        regime = "RISK_ON"
    elif nq == "SHORT" and es == "SHORT":
        regime = "RISK_OFF"
    else:
        regime = "MIXED"

    explanation = (
        f"Regime {regime}. Multi-factor (trend+breadth+volatility+macro). "
        f"Sources: TwelveData={sources['twelvedata']}, FRED={sources['fred']}, "
        f"breadth={sources['breadth']}. "
        "Confidence is measured (backtest), not invented."
    )
    # Warnings (Apex rules: no hedging, correlation awareness).
    warnings = []
    nq_b, es_b = instruments["NQ"].bias, instruments["ES"].bias
    if nq_b in ("LONG", "SHORT") and es_b in ("LONG", "SHORT") and nq_b != es_b:
        warnings.append(
            "NQ and ES point OPPOSITE directions but are highly correlated. "
            "Taking both = de-facto hedge (PROHIBITED on Apex). Pick one.")
    elif nq_b == es_b and nq_b in ("LONG", "SHORT"):
        warnings.append(
            f"NQ and ES are correlated and both {nq_b}. Trading both doubles the "
            "same risk - size accordingly, don't treat as diversified.")
    for s in ("NQ", "ES", "GOLD"):
        sq = instruments[s].signal_quality or {}
        if sq.get("label") == "CONFLICTING":
            warnings.append(f"{s}: factors conflict - low-conviction signal, consider skipping.")
    warnings.append("Reminder: close all positions before market close (Apex rule).")

    # Economic calendar awareness - warn in the window right before a release.
    cal = econ_calendar.upcoming_events(days_ahead=3)
    imminent = cal.get("imminent") or []
    if imminent:
        parts = []
        for e in imminent:
            m = e.get("minutes_until")
            when = ("in " + str(m) + " min") if m and m > 0 else "NOW / just released"
            parts.append(e["event"] + " (" + when + ")")
        warnings.insert(0, "NEWS WINDOW: " + "; ".join(parts) +
                        " - do not open new trades around the release (Apex: no gambling on news).")
    elif cal.get("has_event_today"):
        todays = [e["event"] + " @ " + e.get("time_local", "?")
                  for e in cal["events"] if e["date"] == __import__("datetime").date.today().isoformat()]
        warnings.append("High-impact news later today: " + ", ".join(todays) +
                        " - plan around it.")

    resp = BiasResponse(
        data_ready=td_ok, regime=regime, explanation=explanation,
        sources=sources, macro=macro, warnings=warnings, calendar=cal,
        breadth={"score": round(b_score, 3), **breadth_detail}, **instruments,
    )
    _save_snapshot(resp)
    return resp
