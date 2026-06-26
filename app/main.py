"""MiMo X — entrypoint (Step 4: /health, /bias, /history; versioned under /v1)."""
from datetime import datetime, timezone

from fastapi import FastAPI
from sqlalchemy import text

from app.bias import router as bias_router
from app.config import settings
from app.database import Base, engine
from app.history import router as history_router
from app import models  # noqa: F401  (ensure models are registered before create_all)

app = FastAPI(title=settings.app_name, version="0.4.0")

# Create tables (now includes bias_snapshots).
Base.metadata.create_all(bind=engine)

# ByteByteGo best practice: URL-based versioning. Routers mounted at /v1 ...
app.include_router(bias_router, prefix="/v1", tags=["bias"])
app.include_router(history_router, prefix="/v1", tags=["history"])
# ... and also at root for backward compatibility during transition.
app.include_router(bias_router, tags=["bias"])
app.include_router(history_router, tags=["history"])


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
        "status": "ok",
        "app": settings.app_name,
        "version": "0.4.0",
        "environment": settings.environment,
        "database": "ok" if db_ok else "error",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
def root():
    return {"message": "MiMo X is running. See /health, /bias, /history, /v1/* and /docs."}
