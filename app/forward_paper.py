"""Forward Paper Collector + Confidence scorer.

Logs EVERY actionable signal under the FROZEN candidate_regime_v1 rule with full
context, so after 100-200 trades we can answer "in which regimes does MiMo
degrade?". Outcomes are resolved later by a separate pass.

Confidence here is a TRANSPARENT factor tally (not a fake %): each agreeing
factor adds, each conflicting factor subtracts. It tells MiMo when NOT to trade.
"""
from __future__ import annotations
import json, os, time
from datetime import datetime, timezone

from app.bias import get_bias
from app.regime_monitor import regime_similarity

_LOG = os.getenv("PAPER_LOG_FILE", "/code/data/forward_paper.jsonl")
ALLOWED_REGIMES = {"NQ": {"RISK_ON", "RISK_OFF"}, "ES": {"RISK_ON", "RISK_OFF"},
                   "GOLD": {"NEUTRAL"}}


def _confidence(ib, regime, sim):
    """Transparent factor tally -> (pct, reasons[])."""
    reasons, score, total = [], 0, 0
    # regime match (heaviest factor)
    total += 2
    if regime in ALLOWED_REGIMES.get(ib.symbol, set()):
        score += 2; reasons.append("PASS regime matched (" + regime + ")")
    else:
        reasons.append("FAIL regime mismatch (" + regime + ")")
    # signal quality from live engine
    total += 1
    q = ((ib.signal_quality or {}).get("label") or "").upper()
    if q in ("STRONG",):
        score += 1; reasons.append("PASS signal STRONG")
    elif q in ("MODERATE",):
        score += 0.5; reasons.append("~ signal MODERATE")
    else:
        reasons.append("FAIL signal " + (q or "weak"))
    # regime similarity (is today like the validated era?)
    total += 1
    if sim is not None and sim >= 80:
        score += 1; reasons.append("PASS regime similarity " + str(sim) + "%")
    elif sim is not None and sim >= 60:
        score += 0.5; reasons.append("~ regime similarity " + str(sim) + "%")
    else:
        reasons.append("FAIL regime drift (" + str(sim) + "%)")
    pct = round(100 * score / total) if total else 0
    return pct, reasons


def collect(dry_run=False):
    data = get_bias()
    regime = data.regime
    # Live engine emits RISK_ON/RISK_OFF/MIXED; rule vocab uses NEUTRAL == MIXED.
    if regime == "MIXED":
        regime = "NEUTRAL"
    mon = regime_similarity()
    sim = mon.get("similarity_pct")
    rows = []
    for ib in (data.NQ, data.ES, data.GOLD):
        if ib.bias not in ("LONG", "SHORT"):
            continue
        tp = ib.trade_plan or {}
        allowed = regime in ALLOWED_REGIMES.get(ib.symbol, set())
        conf, reasons = _confidence(ib, regime, sim)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "symbol": ib.symbol, "bias": ib.bias, "regime": regime,
            "regime_similarity": sim, "regime_status": mon.get("status"),
            "entry": tp.get("entry"), "stop": tp.get("stop"), "target": tp.get("target"),
            "atr": tp.get("atr"), "rr": tp.get("rr"),
            "quality": (ib.signal_quality or {}).get("label"), "confidence_pct": conf, "reasons": reasons,
            "rule_allows": allowed,
            "would_trade": allowed and conf >= 60,
            "news_flag": bool((data.calendar or {}).get("imminent")),
            "outcome": None, "r_multiple": None,  # filled later
        }
        rows.append(row)
    if not dry_run:
        os.makedirs(os.path.dirname(_LOG), exist_ok=True)
        with open(_LOG, "a") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    return {"collected": len(rows), "would_trade": sum(1 for r in rows if r["would_trade"]),
            "regime": regime, "similarity": sim, "rows": rows}


def stats():
    """Summary of collected forward paper signals so far."""
    if not os.path.exists(_LOG):
        return {"total": 0, "note": "no forward paper data yet"}
    rows = []
    with open(_LOG) as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    decided = [r for r in rows if r.get("r_multiple") is not None]
    out = {"total_logged": len(rows), "would_trade": sum(1 for r in rows if r.get("would_trade")),
           "decided": len(decided), "progress_to_100": f"{len(decided)}/100"}
    if decided:
        rs = [r["r_multiple"] for r in decided]
        out["expectancy_r"] = round(sum(rs) / len(rs), 3)
    return out