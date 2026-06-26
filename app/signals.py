"""Multi-factor signal engine: trend, breadth, volatility, macro.

Each factor returns a directional score in [-1, +1] (for equities).
We combine them into a raw_score, then classify LONG/SHORT/NEUTRAL.
Confidence is NEVER produced here - only measured performance (backtest)
may later turn raw_score into a real percentage.
"""
from statistics import pstdev

LONG_THRESHOLD = 0.15
SHORT_THRESHOLD = -0.15


def sma(values: list[float], n: int) -> float | None:
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def trend_score(closes: list[float]) -> tuple[float, dict]:
    """Price vs SMA20 and SMA20 vs SMA50. Score in [-1, 1]."""
    price = closes[-1]
    s20, s50 = sma(closes, 20), sma(closes, 50)
    parts, score = {}, 0.0
    if s20 is not None:
        up = price > s20
        score += 0.5 if up else -0.5
        parts["price_vs_sma20"] = "above" if up else "below"
    if s50 is not None and s20 is not None:
        up = s20 > s50
        score += 0.5 if up else -0.5
        parts["sma20_vs_sma50"] = "above" if up else "below"
    detail = {"sma20": round(s20, 4) if s20 else None,
              "sma50": round(s50, 4) if s50 else None, **parts}
    return score, detail


def volatility(closes: list[float], lookback: int = 20) -> tuple[float, dict]:
    """Annualized-ish daily return stdev (%). Returns (vol_pct, detail).

    Volatility is NOT directional - it is a risk flag that dampens conviction.
    """
    window = closes[-(lookback + 1):]
    rets = [(window[i] / window[i - 1] - 1.0) for i in range(1, len(window))]
    if len(rets) < 2:
        return 0.0, {"regime": "UNKNOWN", "daily_pct": None}
    vol = pstdev(rets) * 100.0
    regime = "LOW" if vol < 1.0 else ("NORMAL" if vol < 2.0 else "HIGH")
    return vol, {"regime": regime, "daily_pct": round(vol, 3)}


def breadth_score(basket_closes: dict[str, list[float]]) -> tuple[float, dict]:
    """Fraction of basket members trading above their SMA20. Score in [-1, 1]."""
    above = 0
    total = 0
    members = {}
    for sym, closes in basket_closes.items():
        s20 = sma(closes, 20)
        if s20 is None:
            continue
        total += 1
        is_above = closes[-1] > s20
        above += 1 if is_above else 0
        members[sym] = "above" if is_above else "below"
    if total == 0:
        return 0.0, {"pct_above_sma20": None, "members": members, "available": 0}
    pct = above / total
    score = (pct - 0.5) * 2.0
    return score, {"pct_above_sma20": round(pct, 3), "above": above,
                   "total": total, "members": members}


def macro_score(macro: dict) -> tuple[float, float, dict]:
    """Return (equity_score, gold_score, detail) from VIX & US10Y.

    VIX: rising/high -> risk off (equities -, gold +). Falling/low -> risk on.
    US10Y: rising yields -> mild equity headwind, gold headwind.
    """
    eq = 0.0
    gold = 0.0
    detail = {}
    vix = macro.get("VIX", {})
    if "error" not in vix and vix.get("change") is not None:
        ch = vix["change"]
        lvl = vix.get("latest")
        if ch < 0:
            eq += 0.5; gold -= 0.25
        elif ch > 0:
            eq -= 0.5; gold += 0.25
        if isinstance(lvl, (int, float)) and lvl > 25:
            eq -= 0.25; gold += 0.25
        detail["vix"] = {"latest": lvl, "change": ch}
    y = macro.get("US10Y", {})
    if "error" not in y and y.get("change") is not None:
        ch = y["change"]
        if ch > 0:
            eq -= 0.25; gold -= 0.25
        elif ch < 0:
            eq += 0.25; gold += 0.25
        detail["us10y"] = {"latest": y.get("latest"), "change": ch}
    eq = max(-1.0, min(1.0, eq))
    gold = max(-1.0, min(1.0, gold))
    return eq, gold, detail


def classify(raw: float) -> str:
    if raw > LONG_THRESHOLD:
        return "LONG"
    if raw < SHORT_THRESHOLD:
        return "SHORT"
    return "NEUTRAL"


# Weights per asset class (sum to 1.0).
EQUITY_WEIGHTS = {"trend": 0.45, "breadth": 0.30, "macro": 0.25}
GOLD_WEIGHTS = {"trend": 0.60, "macro": 0.40}


def aggregate_equity(trend: float, breadth: float, macro_eq: float) -> float:
    w = EQUITY_WEIGHTS
    return round(w["trend"] * trend + w["breadth"] * breadth + w["macro"] * macro_eq, 4)


def aggregate_gold(trend: float, macro_gold: float) -> float:
    w = GOLD_WEIGHTS
    return round(w["trend"] * trend + w["macro"] * macro_gold, 4)
