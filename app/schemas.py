"""Pydantic response models for the API."""
from typing import Dict, Literal, Optional
from pydantic import BaseModel

BiasStatus = Literal["DATA_NOT_READY", "LONG", "SHORT", "NEUTRAL"]
Regime = Literal["DATA_NOT_READY", "RISK_ON", "RISK_OFF", "MIXED"]


class InstrumentBias(BaseModel):
    symbol: str
    bias: BiasStatus
    # Stays None until a backtested, calibrated model exists. Never invented.
    confidence: Optional[float] = None
    price: Optional[float] = None
    change_pct: Optional[float] = None
    proxy_symbol: Optional[str] = None
    explanation: str
    error: Optional[str] = None


class BiasResponse(BaseModel):
    data_ready: bool
    regime: Regime
    explanation: str
    sources: Dict[str, str]            # e.g. {"twelvedata": "ok", "fred": "error"}
    macro: Dict[str, dict] = {}
    NQ: InstrumentBias
    ES: InstrumentBias
    GOLD: InstrumentBias
