"""Execution configuration and HARD compliance guards."""
from __future__ import annotations
import os
from dataclasses import dataclass

def _b(name, default="false"):
    return os.getenv(name, default).lower() == "true"

EXECUTION_ENABLED = _b("EXECUTION_ENABLED")
EXECUTION_MODE = os.getenv("EXECUTION_MODE", "paper").lower()   # paper|demo|live
EXECUTION_FIRM = os.getenv("EXECUTION_FIRM", "ftmo").lower()    # ftmo|apex|topstep

# Firms that ban automation outright. Hard block regardless of any flag.
AUTOMATION_BANNED = {"apex", "topstep"}

@dataclass
class RiskLimits:
    # FTMO-style defaults (Challenge $100k). Tune per account.
    account_size: float = 100_000.0
    max_daily_loss_pct: float = 5.0     # FTMO daily loss limit
    max_total_loss_pct: float = 10.0    # FTMO max loss
    risk_per_trade_pct: float = 0.5     # conservative per-trade risk
    max_open_positions: int = 3
    max_capital_allocation: float = 400_000.0  # FTMO rule

LIMITS = RiskLimits()

def compliance_ok() -> tuple[bool, str]:
    if EXECUTION_FIRM in AUTOMATION_BANNED:
        return False, f"{EXECUTION_FIRM.upper()} forbids automation - execution permanently blocked."
    return True, "ok"
