"""Step 7 - forward-test stored snapshots and calibrate confidence.

Uses ONLY stored snapshots (no extra API calls). For each snapshot S at time t
with price p and a directional bias (LONG/SHORT), we find the snapshot closest
to t + horizon and check whether price moved in the predicted direction.
Hit rate becomes the measured accuracy that powers real confidence.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.config import settings
from app.database import get_db
from app.models import BiasSnapshot, Calibration

router = APIRouter()

INSTRUMENTS = {
    "NQ": ("nq_bias", "nq_price"),
    "ES": ("es_bias", "es_price"),
    "GOLD": ("gold_bias", "gold_price"),
}


def _evaluate(db: Session, horizon_hours: int) -> dict:
    rows = db.execute(select(BiasSnapshot).order_by(BiasSnapshot.created_at.asc())).scalars().all()
    horizon = timedelta(hours=horizon_hours)
    tol = timedelta(hours=max(1, horizon_hours // 2))
    results = {k: {"samples": 0, "hits": 0} for k in INSTRUMENTS}

    for i, s in enumerate(rows):
        target = s.created_at + horizon
        # find nearest later snapshot to target time
        best = None
        best_gap = None
        for j in range(i + 1, len(rows)):
            gap = abs(rows[j].created_at - target)
            if best_gap is None or gap < best_gap:
                best, best_gap = rows[j], gap
            if rows[j].created_at > target + tol:
                break
        if best is None or best_gap is None or best_gap > tol:
            continue
        for instr, (bcol, pcol) in INSTRUMENTS.items():
            bias = getattr(s, bcol)
            p0 = getattr(s, pcol)
            p1 = getattr(best, pcol)
            if bias not in ("LONG", "SHORT") or p0 is None or p1 is None:
                continue
            realized = "LONG" if p1 > p0 else ("SHORT" if p1 < p0 else "FLAT")
            if realized == "FLAT":
                continue
            results[instr]["samples"] += 1
            if realized == bias:
                results[instr]["hits"] += 1

    for instr, r in results.items():
        r["hit_rate"] = round(r["hits"] / r["samples"], 4) if r["samples"] else None
    return results


@router.get("/backtest", dependencies=[Depends(require_api_key)])
def backtest(
    horizon_hours: int = Query(None, ge=1, le=720),
    db: Session = Depends(get_db),
):
    h = horizon_hours or settings.backtest_horizon_hours
    res = _evaluate(db, h)
    ready = {k: (v["samples"] >= settings.backtest_min_samples) for k, v in res.items()}
    return {
        "horizon_hours": h,
        "min_samples_for_confidence": settings.backtest_min_samples,
        "results": res,
        "confidence_ready": ready,
        "note": "Confidence stays null until samples >= min_samples_for_confidence.",
    }


@router.post("/backtest/recompute", dependencies=[Depends(require_api_key)])
def recompute(
    horizon_hours: int = Query(None, ge=1, le=720),
    db: Session = Depends(get_db),
):
    h = horizon_hours or settings.backtest_horizon_hours
    res = _evaluate(db, h)
    for instr, r in res.items():
        row = db.execute(select(Calibration).where(Calibration.instrument == instr)).scalar_one_or_none()
        if row is None:
            row = Calibration(instrument=instr)
            db.add(row)
        row.samples = r["samples"]; row.hits = r["hits"]
        row.hit_rate = r["hit_rate"]; row.horizon_hours = h
    db.commit()
    return {"updated": True, "horizon_hours": h, "results": res}
