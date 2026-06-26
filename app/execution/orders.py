"""Order lifecycle (paper mode simulates fills)."""
from __future__ import annotations
import time, uuid
from dataclasses import dataclass, field

@dataclass
class Order:
    symbol: str
    side: str        # LONG|SHORT
    volume: float
    entry: float
    stop: float
    target: float
    status: str = "NEW"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    ts: float = field(default_factory=time.time)

class OrderManager:
    def __init__(self):
        self._orders: list[Order] = []
    def record(self, o: Order) -> Order:
        self._orders.append(o); return o
    def all(self):
        return list(self._orders)
