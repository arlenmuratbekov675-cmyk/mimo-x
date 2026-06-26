"""Open position tracking."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Position:
    symbol: str
    side: str
    volume: float
    entry: float
    stop: float
    target: float

class PositionManager:
    def __init__(self):
        self._open: dict[str, Position] = {}
    def open(self, p: Position):
        self._open[p.symbol] = p
    def close(self, symbol: str):
        self._open.pop(symbol, None)
    def count(self) -> int:
        return len(self._open)
    def all(self):
        return list(self._open.values())
