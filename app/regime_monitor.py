"""Regime Monitor - detects when current market drifts from the validated regime.

Philosophy: "a strategy that knows when it stops working."

We characterize the regime candidate_regime_v1 was validated on (recent strong
windows) by a feature vector, then score how SIMILAR today's market is. If
similarity drops, MiMo recommends paper-only.
"""
from __future__ import annotations
import os
import statistics

from app.datasources import fetch_td_ohlc, fetch_td_series, fetch_fred_series


def _sma(vals, n):
    return sum(vals[-n:]) / n if len(vals) >= n else None


def _features(spy, vix):
    """Feature vector describing the current regime."""
    f = {}
    if spy and len(spy) >= 50:
        s50 = _sma(spy, 50)
        f["spy_vs_sma50_pct"] = round((spy[-1] / s50 - 1) * 100, 2) if s50 else None
        rets = [(spy[i] / spy[i - 1] - 1) for i in range(-20, 0)]
        f["spy_realized_vol_pct"] = round(statistics.pstdev(rets) * 100, 2)
    if vix and len(vix) >= 20:
        f["vix_level"] = round(vix[-1], 2)
        vsma = _sma(vix, 20)
        f["vix_vs_sma20"] = round(vix[-1] - vsma, 2) if vsma else None
    return f


# Reference profile = center of the recent VALIDATED regime (strong WF windows).
# Bands are tolerances; similarity falls off as today moves outside them.
_REFERENCE = {
    "spy_vs_sma50_pct": (3.0, 8.0),     # (center, half-width)
    "spy_realized_vol_pct": (1.0, 1.2),
    "vix_level": (16.0, 9.0),
    "vix_vs_sma20": (-1.0, 5.0),
}


def regime_similarity():
    try:
        spy = fetch_td_ohlc("SPY", outputsize=80).get("closes") or []
    except Exception:
        spy = []
    try:
        vix = fetch_fred_series("VIXCLS", limit=80).get("values") or []
    except Exception:
        vix = []
    feats = _features(spy, vix)
    scores, detail = [], {}
    for k, (center, half) in _REFERENCE.items():
        v = feats.get(k)
        if v is None or half == 0:
            continue
        dist = abs(v - center) / half        # 0 = bullseye, 1 = edge of band
        s = max(0.0, 1.0 - dist)             # linear falloff, floored at 0
        scores.append(s)
        detail[k] = {"value": v, "center": center, "score": round(s, 2)}
    similarity = round(100 * statistics.mean(scores), 1) if scores else None
    if similarity is None:
        status, rec = "UNKNOWN", "Insufficient data - paper mode only."
    elif similarity >= 80:
        status, rec = "MATCHED", "Regime matches validated conditions."
    elif similarity >= 60:
        status, rec = "DRIFTING", "Regime drifting - reduce size, watch closely."
    else:
        status, rec = "DIVERGED", ("Current regime differs significantly from "
                                   "validated regime. Recommendation: paper mode only.")
    return {"similarity_pct": similarity, "status": status,
            "recommendation": rec, "features": feats, "detail": detail}

import json as _json
from datetime import date as _date

_SIM_LOG = os.getenv("SIM_LOG_FILE", "/code/data/regime_similarity.jsonl")


def log_similarity_daily():
    """Append today's similarity once per day (display-only, no decisions)."""
    res = regime_similarity()
    sim = res.get("similarity_pct")
    if sim is None:
        return res
    os.makedirs(os.path.dirname(_SIM_LOG), exist_ok=True)
    today = _date.today().isoformat()
    if os.path.exists(_SIM_LOG):
        with open(_SIM_LOG) as f:
            lines = f.read().strip().splitlines()
        if lines:
            try:
                if _json.loads(lines[-1]).get("date") == today:
                    return res  # already logged today
            except Exception:
                pass
    with open(_SIM_LOG, "a") as f:
        f.write(_json.dumps({"date": today, "similarity": sim,
                             "status": res.get("status")}) + "\n")
    return res


def similarity_history(limit=60):
    if not os.path.exists(_SIM_LOG):
        return []
    rows = []
    with open(_SIM_LOG) as f:
        for line in f:
            try:
                rows.append(_json.loads(line))
            except Exception:
                pass
    return rows[-limit:]
