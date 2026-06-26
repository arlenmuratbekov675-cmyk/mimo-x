"""Step 4 — /history endpoint with pagination (limit/offset)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BiasSnapshot

router = APIRouter()


@router.get("/history")
def list_history(
    limit: int = Query(10, ge=1, le=100, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Rows to skip"),
    db: Session = Depends(get_db),
):
    """Most-recent-first list of stored bias snapshots, paginated."""
    total = db.scalar(select(func.count()).select_from(BiasSnapshot)) or 0
    rows = (
        db.execute(
            select(BiasSnapshot)
            .order_by(BiasSnapshot.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    items = [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() + "Z" if r.created_at else None,
            "data_ready": r.data_ready,
            "regime": r.regime,
            "NQ": {"bias": r.nq_bias, "price": r.nq_price, "change_pct": r.nq_change_pct},
            "ES": {"bias": r.es_bias, "price": r.es_price, "change_pct": r.es_change_pct},
            "GOLD": {"bias": r.gold_bias, "price": r.gold_price, "change_pct": r.gold_change_pct},
        }
        for r in rows
    ]
    return {"total": total, "limit": limit, "offset": offset, "count": len(items), "items": items}
