"""Replay / walk-forward backtest engine.

HONEST SCOPE: replays the TREND + VOLATILITY core of the live bias engine - the
factors we can faithfully reconstruct from historical daily bars. It does NOT
replay live breadth/macro (those need point-in-time sector + FRED snapshots we
don't store historically yet). So treat replay stats as a lower bound / sanity
check on the trend core, not proof of the full multi-factor system.

Outputs real, auditable statistics so we can judge edge before risking money.
"""
from __future__ import annotations
import statistics
from dataclasses import dataclass, asdict

from app.datasources import fetch_td_ohlc

PROXY = {"NQ": "QQQ", "ES": "SPY", "GOLD": "GLD"}


def _sma(vals, n):
    return sum(vals[-n:]) / n if len(vals) >= n else None


def _atr(highs, lows, closes, n=14):
    if len(closes) < n + 1:
        return None
    trs = []
    for i in range(-n, 0):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i - 1]),
                 abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    return sum(trs) / n


@dataclass
class Trade:
    symbol: str
    side: str
    entry: float
    stop: float
    target: float
    outcome: str        # WIN|LOSS|TIMEOUT
    r_multiple: float
    bars_held: int


def _signal(closes, highs, lows):
    """Trend core: LONG if price>SMA20>SMA50, SHORT if price<SMA20<SMA50."""
    s20, s50 = _sma(closes, 20), _sma(closes, 50)
    if s20 is None or s50 is None:
        return None
    p = closes[-1]
    if p > s20 > s50:
        return "LONG"
    if p < s20 < s50:
        return "SHORT"
    return None


def replay_symbol(symbol: str, lookback: int = 400, timeout_bars: int = 15,
                  rr: float = 2.0, atr_stop_mult: float = 1.5) -> list[Trade]:
    proxy = PROXY.get(symbol, symbol)
    try:
        d = fetch_td_ohlc(proxy, outputsize=lookback)
    except Exception:
        return []
    highs = d.get("highs") or []
    lows = d.get("lows") or []
    closes = d.get("closes") or []
    if len(closes) < 80:
        return []

    trades: list[Trade] = []
    i = 50
    while i < len(closes) - 1:
        side = _signal(closes[: i + 1], highs[: i + 1], lows[: i + 1])
        atr = _atr(highs[: i + 1], lows[: i + 1], closes[: i + 1])
        if side is None or not atr:
            i += 1
            continue
        entry = closes[i]
        if side == "LONG":
            stop = entry - atr_stop_mult * atr
            target = entry + atr_stop_mult * atr * rr
        else:
            stop = entry + atr_stop_mult * atr
            target = entry - atr_stop_mult * atr * rr
        # resolve forward
        outcome, r, held = "TIMEOUT", 0.0, 0
        for j in range(i + 1, min(i + 1 + timeout_bars, len(closes))):
            held = j - i
            hi, lo = highs[j], lows[j]
            if side == "LONG":
                if lo <= stop:
                    outcome, r = "LOSS", -1.0; break
                if hi >= target:
                    outcome, r = "WIN", rr; break
            else:
                if hi >= stop:
                    outcome, r = "LOSS", -1.0; break
                if lo <= target:
                    outcome, r = "WIN", rr; break
        if outcome == "TIMEOUT":
            # mark-to-market at exit close
            exit_close = closes[min(i + timeout_bars, len(closes) - 1)]
            move = (exit_close - entry) if side == "LONG" else (entry - exit_close)
            r = round(move / (atr_stop_mult * atr), 2)
        trades.append(Trade(symbol, side, round(entry, 2), round(stop, 2),
                            round(target, 2), outcome, round(r, 2), held))
        i += max(held, 1)  # no overlapping trades
    return trades


def _stats(trades: list[Trade]) -> dict:
    if not trades:
        return {"samples": 0, "note": "no trades generated"}
    rs = [t.r_multiple for t in trades]
    wins = [t for t in trades if t.outcome == "WIN"]
    losses = [t for t in trades if t.outcome == "LOSS"]
    # equity curve in R for max drawdown
    eq, peak, maxdd = 0.0, 0.0, 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        maxdd = min(maxdd, eq - peak)
    n = len(trades)
    return {
        "samples": n,
        "wins": len(wins), "losses": len(losses),
        "timeouts": sum(1 for t in trades if t.outcome == "TIMEOUT"),
        "win_rate_pct": round(100 * len(wins) / n, 1),
        "avg_r": round(statistics.mean(rs), 3),
        "expectancy_r": round(statistics.mean(rs), 3),
        "total_r": round(sum(rs), 2),
        "max_drawdown_r": round(maxdd, 2),
        "best_r": round(max(rs), 2), "worst_r": round(min(rs), 2),
    }


def run_replay(lookback: int = 400) -> dict:
    all_trades, per_symbol = [], {}
    for sym in PROXY:
        t = replay_symbol(sym, lookback=lookback)
        per_symbol[sym] = _stats(t)
        all_trades.extend(t)
    return {
        "scope": "trend+volatility core only (breadth/macro not reconstructed)",
        "lookback_bars": lookback,
        "overall": _stats(all_trades),
        "per_symbol": per_symbol,
        "sample_trades": [asdict(t) for t in all_trades[:10]],
    }
