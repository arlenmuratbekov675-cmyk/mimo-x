# MiMo X

Clean rebuild of the MiMo market dashboard as a proper, long-lived platform.
**Step 0 — foundation only.** No trading logic, no data sources yet — just a
runnable FastAPI + SQLite skeleton you can build on.

## Stack
- **FastAPI** — web framework / API
- **SQLite** + **SQLAlchemy 2.0** — database (swap to PostgreSQL later, no rewrite)
- **Pydantic Settings** — config from `.env`
- **Docker Compose** — one-command run

## Project layout
```
mimo-x/
├── app/
│   ├── __init__.py
│   ├── config.py       # settings loaded from .env
│   ├── database.py     # SQLAlchemy engine, session, Base
│   ├── models.py       # ORM models (empty for now)
│   └── main.py         # FastAPI app + /health endpoint
├── .env.example        # copy to .env
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Run it

### Option A — Local Python (fastest for dev)
```powershell
cd mimo-x
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

### Option B — Docker Compose (one command)
```powershell
cd mimo-x
copy .env.example .env
docker compose up --build
```

## Verify
- Health check: http://localhost:8000/health
- Interactive API docs: http://localhost:8000/docs
- Root: http://localhost:8000/

Expected `/health` response:
```json
{ "status": "ok", "app": "MiMo X", "database": "ok", ... }
```

## Roadmap (next steps — not built yet)
1. **Step 1** — FRED integration (free, official, stable) → DB → API
2. **Step 2** — TwelveData prices + background scheduler
3. **Step 3** — History storage (snapshots of prices + indicators + outcome)
4. **Step 4** — Indicators & bias (modular, weighted)
5. **Step 5** — Backtest engine (Win Rate / Profit Factor / Max Drawdown)
6. **Step 6** — AI brain + explanations (confidence from real calibration)
7. **Step 7** — Trading terminal frontend
8. **Step 8** — Sai agent automation (nightly backtests, reports, auto-PRs)
