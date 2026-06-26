"""MiMo X entrypoint - Step 5/6/7: cache, auth, multi-factor bias, backtest."""
from datetime import datetime, timezone

from fastapi import FastAPI
from sqlalchemy import text

from app.backtest import router as backtest_router
from app.bias import router as bias_router
from app.config import settings
from app.database import Base, engine
from app.datasources import cache_info
from app.history import router as history_router
from app import models  # noqa: F401

app = FastAPI(title=settings.app_name, version="0.5.0")

Base.metadata.create_all(bind=engine)

for r in (bias_router, history_router, backtest_router):
    app.include_router(r, prefix="/v1")
    app.include_router(r)


@app.get("/health")
def health():
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok", "app": settings.app_name, "version": "0.5.0",
        "environment": settings.environment, "database": "ok" if db_ok else "error",
        "auth": "enabled" if settings.api_key else "disabled",
        "cache": cache_info(),
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
def root():
    return {"message": "MiMo X. See /health, /bias, /history, /backtest, /v1/*, /docs."}
