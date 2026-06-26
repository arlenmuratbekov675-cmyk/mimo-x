"""Replay engine v2: regime-segmented walk-forward backtest.

Insight from prior run: a hard breadth>50% filter HURT expectancy, so it's out.
Instead we now SEGMENT results by market regime (Risk-ON / Risk-OFF / Neutral)
to see WHERE the edge actually lives, rather than forcing a global gate.

Regime is derived from reconstructable data:
  - SPY trend vs SMA50  (broad equity direction)
  - VIX level vs SMA20  (VIX from FRED VIXCLS - daily history, now available)

GOLD keeps trend+vol only (its drivers are macro, not equity breadth).
All stats are real and auditable. No money at risk.
"""
from __future__ import annotations
import statistics
from dataclasses import dataclass

from app.datasources import fetch_td_ohlc, fetch_td_series, fetch_fred_series

PROXY = {"NQ": "QQQ", "ES": "SPY", "GOLD": "GLD"}

# candidate_regime_v1 (EXPERIMENTAL HYPOTHESIS - not a proven law).
# Passed recent out-of-sample; long-history robustness under test.
# equities have edge in trending regimes; GOLD has edge in NEUTRAL only.
ALLOWED_REGIMES = {
    "NQ": {"RISK_ON", "RISK_OFF"},
    "ES": {"RISK_ON", "RISK_OFF"},
    "GOLD": {"NEUTRAL"},
}


def _sma(vals, n):
    return sum(vals[-n:]) / n if len(vals) >= n else None


def _atr(highs, lows, closes, n=14):
    if len(closes) < n + 1:
        return None
    trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
               abs(lows[i] - closes[i - 1])) for i in range(-n, 0)]
    return sum(trs) / n


def _signal(closes):
    s20, s50 = _sma(closes, 20), _sma(closes, 50)
    if s20 is None or s50 is None:
        return None
    p = closes[-1]
    if p > s20 > s50:
        return "LONG"
    if p < s20 < s50:
        return "SHORT"
    return None


@dataclass
class Trade:
    symbol: str
    side: str
    outcome: str
    r_multiple: float
    regime: str


def _regime_at(i, spy_closes, vix_vals):
    """Risk-ON / Risk-OFF / Neutral from SPY trend + VIX level."""
    spy_s50 = _sma(spy_closes[: i + 1], 50)
    if spy_s50 is None:
        return "NEUTRAL"
    spy_up = spy_closes[i] > spy_s50
    vix_calm = True
    if vix_vals and i < len(vix_vals):
        vsma = _sma(vix_vals[: i + 1], 20)
        if vsma is not None:
            vix_calm = vix_vals[i] < vsma
    if spy_up and vix_calm:
        return "RISK_ON"
    if (not spy_up) and (not vix_calm):
        return "RISK_OFF"
    return "NEUTRAL"


def replay_symbol(symbol, closes, highs, lows, spy_closes, vix_vals,
                  timeout_bars=15, rr=2.0, atr_stop_mult=1.5, regime_aware=False):
    trades = []
    i = 50
    while i < len(closes) - 1:
        side = _signal(closes[: i + 1])
        atr = _atr(highs[: i + 1], lows[: i + 1], closes[: i + 1])
        if side is None or not atr:
            i += 1
            continue
        regime = _regime_at(i, spy_closes, vix_vals)
        if regime_aware and regime not in ALLOWED_REGIMES.get(symbol, set()):
            i += 1
            continue
        entry = closes[i]
        if side == "LONG":
            stop, target = entry - atr_stop_mult * atr, entry + atr_stop_mult * atr * rr
        else:
            stop, target = entry + atr_stop_mult * atr, entry - atr_stop_mult * atr * rr
        outcome, r, held = "TIMEOUT", 0.0, 0
        for j in range(i + 1, min(i + 1 + timeout_bars, len(closes))):
            held = j - i
            if side == "LONG":
                if lows[j] <= stop:
                    outcome, r = "LOSS", -1.0; break
                if highs[j] >= target:
                    outcome, r = "WIN", rr; break
            else:
                if highs[j] >= stop:
                    outcome, r = "LOSS", -1.0; break
                if lows[j] <= target:
                    outcome, r = "WIN", rr; break
        if outcome == "TIMEOUT":
            exit_close = closes[min(i + timeout_bars, len(closes) - 1)]
            move = (exit_close - entry) if side == "LONG" else (entry - exit_close)
            r = round(move / (atr_stop_mult * atr), 2)
        trades.append(Trade(symbol, side, outcome, round(r, 2), regime))
        i += max(held, 1)
    return trades


def _stats(trades):
    if not trades:
        return {"samples": 0}
    rs = [t.r_multiple for t in trades]
    wins = sum(1 for t in trades if t.outcome == "WIN")
    losses = sum(1 for t in trades if t.outcome == "LOSS")
    decided = wins + losses
    eq = peak = maxdd = 0.0
    for r in rs:
        eq += r; peak = max(peak, eq); maxdd = min(maxdd, eq - peak)
    return {
        "samples": len(trades), "wins": wins, "losses": losses,
        "decided_win_rate_pct": round(100 * wins / decided, 1) if decided else None,
        "expectancy_r": round(statistics.mean(rs), 3),
        "total_r": round(sum(rs), 2), "max_drawdown_r": round(maxdd, 2),
    }


def _by_regime(trades):
    out = {}
    for reg in ("RISK_ON", "RISK_OFF", "NEUTRAL"):
        out[reg] = _stats([t for t in trades if t.regime == reg])
    return out


def _slice_ctx(c, h, lo, spy_a, vix_a, start, end):
    return (c[start:end], h[start:end], lo[start:end],
            spy_a[start:end], (vix_a[start:end] if vix_a else None))


def run_split(lookback=400):
    """Out-of-sample test. Rule is FROZEN (ALLOWED_REGIMES). Train=first half,
    Test=second half. We do NOT re-derive anything - just apply the same rule
    to a period it was never tuned on."""
    try:
        spy = fetch_td_ohlc("SPY", outputsize=lookback).get("closes") or []
    except Exception:
        spy = []
    try:
        vix = fetch_fred_series("VIXCLS", limit=lookback).get("values") or []
    except Exception:
        vix = []
    out = {"rule": "NQ/ES: RISK_ON|RISK_OFF only; GOLD: NEUTRAL only (FROZEN)",
           "vix_available": bool(vix), "train": {}, "test": {}, "per_symbol": {}}
    train_all, test_all = [], []
    for sym in PROXY:
        try:
            d = fetch_td_ohlc(PROXY[sym], outputsize=lookback)
        except Exception:
            continue
        closes, highs, lows = d.get("closes") or [], d.get("highs") or [], d.get("lows") or []
        L = min([len(closes), len(spy) or len(closes)] + ([len(vix)] if vix else []))
        c, h, lo = closes[-L:], highs[-L:], lows[-L:]
        spy_a = spy[-L:] if spy else c
        vix_a = vix[-L:] if vix else None
        if len(c) < 120:
            continue
        mid = len(c) // 2
        # train = first half, test = second half
        tr = _slice_ctx(c, h, lo, spy_a, vix_a, 0, mid)
        te = _slice_ctx(c, h, lo, spy_a, vix_a, mid, len(c))
        t_tr = replay_symbol(sym, *tr, regime_aware=True)
        t_te = replay_symbol(sym, *te, regime_aware=True)
        out["per_symbol"][sym] = {"train": _stats(t_tr), "test": _stats(t_te)}
        train_all += t_tr; test_all += t_te
    out["train"] = _stats(train_all)
    out["test"] = _stats(test_all)
    return out


def run_walkforward(lookback=1000, test_size=100, step=50):
    """Rolling walk-forward of candidate_regime_v1 (FROZEN rule).

    Slide a test window across history; evaluate the same rule on each window it
    has never been tuned on. Reports per-window expectancy + stability metrics.
    Train portion is conceptual only (rule is fixed, nothing is re-fit).
    """
    import statistics as _st
    try:
        spy = fetch_td_ohlc("SPY", outputsize=lookback).get("closes") or []
    except Exception:
        spy = []
    try:
        vix = fetch_fred_series("VIXCLS", limit=lookback).get("values") or []
    except Exception:
        vix = []
    # preload symbol bars
    data = {}
    minlen = None
    for sym in PROXY:
        try:
            d = fetch_td_ohlc(PROXY[sym], outputsize=lookback)
        except Exception:
            continue
        data[sym] = d
        l = len(d.get("closes") or [])
        minlen = l if minlen is None else min(minlen, l)
    L = min([x for x in [minlen, len(spy) or minlen] + ([len(vix)] if vix else []) if x])
    spy_a = spy[-L:] if spy else None
    vix_a = vix[-L:] if vix else None

    windows = []
    start = 60  # need warmup for SMA50/regime
    while start + test_size <= L:
        s, e = start, start + test_size
        win_trades = []
        for sym in PROXY:
            if sym not in data:
                continue
            c = (data[sym]["closes"])[-L:]
            h = (data[sym]["highs"])[-L:]
            lo = (data[sym]["lows"])[-L:]
            sp = spy_a if spy_a else c
            t = replay_symbol(sym, c[s:e], h[s:e], lo[s:e],
                              sp[s:e], (vix_a[s:e] if vix_a else None),
                              regime_aware=True)
            win_trades += t
        st = _stats(win_trades)
        windows.append({"start": s, "end": e, "expectancy_r": st.get("expectancy_r"),
                        "samples": st.get("samples"), "total_r": st.get("total_r"),
                        "win_rate": st.get("decided_win_rate_pct")})
        start += step

    exps = [w["expectancy_r"] for w in windows if w["samples"] and w["samples"] >= 3]
    summary = {}
    if exps:
        positive = sum(1 for x in exps if x > 0)
        summary = {
            "windows_evaluated": len(exps),
            "mean_expectancy_r": round(_st.mean(exps), 3),
            "median_expectancy_r": round(_st.median(exps), 3),
            "stdev_expectancy_r": round(_st.pstdev(exps), 3) if len(exps) > 1 else 0,
            "pct_positive_windows": round(100 * positive / len(exps), 1),
            "worst_window_r": round(min(exps), 3),
            "best_window_r": round(max(exps), 3),
        }
    return {"rule": "candidate_regime_v1 (FROZEN, experimental)",
            "lookback": lookback, "test_size": test_size, "step": step,
            "vix_available": bool(vix), "summary": summary, "windows": windows}


def run_replay(lookback=400):
    # context
    try:
        spy = fetch_td_ohlc("SPY", outputsize=lookback).get("closes") or []
    except Exception:
        spy = []
    try:
        vix = fetch_fred_series("VIXCLS", limit=lookback).get("values") or []
    except Exception:
        vix = []
    result = {"scope": "regime-segmented (SPY trend + FRED VIX); GOLD trend+vol",
              "lookback_bars": lookback, "vix_available": bool(vix),
              "per_symbol": {}, "by_regime": {}}
    agg = []
    agg_aware = []
    for sym in PROXY:
        try:
            d = fetch_td_ohlc(PROXY[sym], outputsize=lookback)
        except Exception:
            continue
        closes, highs, lows = d.get("closes") or [], d.get("highs") or [], d.get("lows") or []
        L = min([len(closes), len(spy) or len(closes)] + ([len(vix)] if vix else []))
        c, h, lo = closes[-L:], highs[-L:], lows[-L:]
        spy_a = spy[-L:] if spy else c
        vix_a = vix[-L:] if vix else None
        if len(c) < 80:
            continue
        t = replay_symbol(sym, c, h, lo, spy_a, vix_a, regime_aware=False)
        ta = replay_symbol(sym, c, h, lo, spy_a, vix_a, regime_aware=True)
        result["per_symbol"][sym] = {"overall": _stats(t), "by_regime": _by_regime(t),
                                     "regime_aware": _stats(ta)}
        agg += t
        agg_aware.extend(ta)
    result["overall"] = _stats(agg)
    result["by_regime"] = _by_regime(agg)
    result["regime_aware_overall"] = _stats(agg_aware)
    return result