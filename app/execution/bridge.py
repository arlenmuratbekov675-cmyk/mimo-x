"""Broker adapter - swappable. PaperBridge works NOW; CTraderBridge after KYC.

The orchestrator only ever talks to BaseBridge, so swapping brokers later means
writing one new subclass - nothing upstream changes.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from app.execution.orders import Order
from app.execution import oauth

class BaseBridge(ABC):
    name = "base"
    @abstractmethod
    def connected(self) -> bool: ...
    @abstractmethod
    def submit(self, order: Order) -> dict: ...

class PaperBridge(BaseBridge):
    """Fully functional simulation - usable today while KYC is pending."""
    name = "paper"
    def connected(self) -> bool:
        return True
    def submit(self, order: Order) -> dict:
        order.status = "FILLED_PAPER"
        return {"ok": True, "mode": "paper", "order_id": order.id,
                "filled_at": order.entry, "note": "simulated fill (no real money)"}

class CTraderBridge(BaseBridge):
    """Real cTrader Open API adapter. Requires KYC-Active app + OAuth token.

    Protobuf-over-TLS client (demo.ctraderapi.com:5035 / live:5035) will be
    implemented once we have a token to test against - intentionally not built
    blind. Until then it refuses clearly instead of pretending.
    """
    name = "ctrader"
    def connected(self) -> bool:
        return oauth.is_authorized()
    def submit(self, order: Order) -> dict:
        if not self.connected():
            return {"ok": False, "error": "cTrader not authorized yet (awaiting KYC + OAuth token)"}
        return {"ok": False, "error": "cTrader protobuf client not implemented yet - build after first token test"}

def get_bridge(mode: str) -> BaseBridge:
    return PaperBridge() if mode in ("paper", "demo") else CTraderBridge()
