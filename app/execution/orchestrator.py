"""Thin orchestrator: bias signal -> compliance -> risk -> bridge.

This is the ONLY thing the rest of MiMo imports. It refuses to act unless every
gate passes, so accidental live trades are structurally impossible.
"""
from __future__ import annotations
from app.execution import config
from app.execution.risk import position_size, preflight, RiskRejection
from app.execution.orders import Order, OrderManager
from app.execution.positions import Position, PositionManager
from app.execution.bridge import get_bridge

class Orchestrator:
    def __init__(self):
        self.orders = OrderManager()
        self.positions = PositionManager()
        self.bridge = get_bridge(config.EXECUTION_MODE)

    def status(self) -> dict:
        ok, reason = config.compliance_ok()
        return {
            "enabled": config.EXECUTION_ENABLED,
            "mode": config.EXECUTION_MODE,
            "firm": config.EXECUTION_FIRM,
            "compliance_ok": ok, "compliance_note": reason,
            "bridge": self.bridge.name,
            "bridge_connected": self.bridge.connected(),
            "open_positions": self.positions.count(),
        }

    def execute_signal(self, symbol, side, entry, stop, target) -> dict:
        ok, reason = config.compliance_ok()
        if not ok:
            return {"ok": False, "stage": "compliance", "error": reason}
        if not config.EXECUTION_ENABLED:
            return {"ok": False, "stage": "flag", "error": "EXECUTION_ENABLED=false (analyst mode)"}
        if config.EXECUTION_MODE == "live" and not self.bridge.connected():
            return {"ok": False, "stage": "auth", "error": "live bridge not connected"}
        try:
            preflight(self.positions.count())
            vol = position_size(entry, stop)
        except RiskRejection as e:
            return {"ok": False, "stage": "risk", "error": str(e)}
        order = self.orders.record(Order(symbol, side, vol, entry, stop, target))
        result = self.bridge.submit(order)
        if result.get("ok"):
            self.positions.open(Position(symbol, side, vol, entry, stop, target))
        return {"ok": result.get("ok"), "stage": "submit", "volume": vol,
                "order_id": order.id, "bridge_result": result}

_orc = Orchestrator()
def get_orchestrator() -> Orchestrator:
    return _orc
