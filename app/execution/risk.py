"""Risk manager - position sizing + FTMO loss-limit guards."""
from __future__ import annotations
from app.execution import config
from app.execution.account import get_account

class RiskRejection(Exception):
    pass

def position_size(entry: float, stop: float) -> float:
    """Contracts/units sized so a stop-out loses risk_per_trade_pct of balance."""
    acct = get_account()
    risk_cash = acct.balance * (config.LIMITS.risk_per_trade_pct / 100.0)
    per_unit_risk = abs(entry - stop)
    if per_unit_risk <= 0:
        raise RiskRejection("entry and stop are equal - cannot size")
    return round(risk_cash / per_unit_risk, 2)

def preflight(open_positions: int) -> None:
    acct = get_account()
    if acct.daily_loss_pct() >= config.LIMITS.max_daily_loss_pct:
        raise RiskRejection("daily loss limit reached - no new trades today")
    if open_positions >= config.LIMITS.max_open_positions:
        raise RiskRejection("max open positions reached")
