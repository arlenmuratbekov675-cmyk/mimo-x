"""Account state snapshot (paper mode keeps it in-memory)."""
from __future__ import annotations
from dataclasses import dataclass, field
from app.execution import config

@dataclass
class AccountState:
    balance: float = field(default_factory=lambda: config.LIMITS.account_size)
    equity: float = field(default_factory=lambda: config.LIMITS.account_size)
    realized_pnl_today: float = 0.0
    ctid_trader_account_id: int | None = None  # filled after OAuth

    def daily_loss_pct(self) -> float:
        if self.balance <= 0:
            return 0.0
        return max(0.0, -self.realized_pnl_today) / self.balance * 100.0

_state = AccountState()

def get_account() -> AccountState:
    return _state
