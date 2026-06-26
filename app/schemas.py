"""Pydantic response models."""
from pydantic import BaseModel


class InstrumentBias(BaseModel):
    symbol: str
    bias: str                      # LONG | SHORT | NEUTRAL | DATA_NOT_READY
    confidence: float | None = None  # real % only after backtest; else null
    price: float | None = None
    change_pct: float | None = None
    raw_score: float | None = None
    proxy_symbol: str | None = None
    factors: dict | None = None
    volatility: dict | None = None
    explanation: str
    error: str | None = None


class BiasResponse(BaseModel):
    data_ready: bool
    regime: str
    explanation: str
    sources: dict
    macro: dict
    breadth: dict | None = None
    NQ: InstrumentBias
    ES: InstrumentBias
    GOLD: InstrumentBias
