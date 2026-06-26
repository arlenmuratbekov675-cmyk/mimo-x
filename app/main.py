"""MiMo X — application entrypoint (Step 1: /health + /bias)."""
from datetime import datetime, timezone

from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.database import Base, engine
from app.bias import router as bias_router

app = FastAPI(title=settings.app_name, version="0.3.0")

# Create tables on startup (no-op for now — no models yet).
Base.metadata.create_all(bind=engine)

# Register routers
app.include_router(bias_router, tags=["bias"])


@app.get("/health")
def health():
    """Liveness + DB connectivity probe."""
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "0.3.0",
        "environment": settings.environment,
        "database": "ok" if db_ok else "error",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
def root():
    return {"message": "MiMo X is running. See /health, /bias and /docs."}
