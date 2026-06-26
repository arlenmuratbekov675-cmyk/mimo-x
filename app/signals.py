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
    dxy = macro.get("DXY", {})
    if "error" not in dxy and dxy.get("change") is not None:
        ch = dxy["change"]
        # Strong dollar (rising DXY) = headwind for US equities AND gold.
        if ch > 0:
            eq -= 0.25; gold -= 0.5
        elif ch < 0:
            eq += 0.25; gold += 0.5
        detail["dxy"] = {"latest": dxy.get("latest"), "change": ch}
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


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    """Average True Range over the last `period` bars."""
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return None
    trs = []
    for i in range(n - period, n):
        if i == 0:
            continue
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        trs.append(max(hl, hc, lc))
    if not trs:
        return None
    return sum(trs) / len(trs)


# Risk model (in ATR multiples).
STOP_ATR_MULT = 1.5
RR_TARGET = 2.0  # reward : risk


def trade_plan(bias: str, price: float, atr_value: float | None) -> dict | None:
    """ATR-based entry/stop/target. Only for directional (LONG/SHORT) bias.

    NOTE: levels are on the PROXY ETF scale (QQQ/SPY/GLD), so treat them as a
    directional/relative reference until a real futures feed is connected.
    """
    if bias not in ("LONG", "SHORT") or not atr_value or price is None:
        return None
    risk = STOP_ATR_MULT * atr_value
    reward = RR_TARGET * risk
    if bias == "LONG":
        entry, stop, target = price, price - risk, price + reward
    else:
        entry, stop, target = price, price + risk, price - reward
    return {
        "direction": bias,
        "entry": round(entry, 4),
        "stop": round(stop, 4),
        "target": round(target, 4),
        "risk_per_unit": round(risk, 4),
        "reward_per_unit": round(reward, 4),
        "risk_pct": round(risk / price * 100, 3),
        "reward_pct": round(reward / price * 100, 3),
        "rr": RR_TARGET,
        "atr": round(atr_value, 4),
        "atr_pct": round(atr_value / price * 100, 3),
        "basis": "proxy ETF (directional reference; not exact futures levels)",
    }


def signal_quality(raw: float, factors: dict) -> dict:
    """Grade conviction by factor agreement + raw magnitude.

    Returns {label, score, agree, total, note}.
    CONFLICTING = factors point in different directions (low trust).
    """
    bias = classify(raw)
    if bias == "NEUTRAL":
        return {"label": "NEUTRAL", "agree": 0, "total": 0,
                "note": "No directional edge (raw near zero)."}

    want = 1 if raw > 0 else -1
    contribs = []
    t = factors.get("trend", {})
    if t.get("price_vs_sma20"):
        contribs.append(("price_vs_sma20", 1 if t["price_vs_sma20"] == "above" else -1))
    if t.get("sma20_vs_sma50"):
        contribs.append(("sma20_vs_sma50", 1 if t["sma20_vs_sma50"] == "above" else -1))
    if "breadth" in factors and factors["breadth"].get("score") is not None:
        bs = factors["breadth"]["score"]
        contribs.append(("breadth", 1 if bs > 0 else (-1 if bs < 0 else 0)))
    macro = factors.get("macro", {})
    ms = macro.get("equity_score", macro.get("gold_score"))
    if ms is not None:
        contribs.append(("macro", 1 if ms > 0 else (-1 if ms < 0 else 0)))

    total = len(contribs)
    agree = sum(1 for _, d in contribs if d == want)
    disagree = sum(1 for _, d in contribs if d == -want)
    mag = abs(raw)

    if total and agree == total and mag >= 0.35:
        label = "STRONG"
    elif disagree >= agree:
        label = "CONFLICTING"
    elif agree >= disagree and mag >= 0.2:
        label = "MODERATE"
    else:
        label = "WEAK"

    note = f"{agree}/{total} factors agree with {bias}."
    if label == "CONFLICTING":
        note += " Factors disagree - treat with caution."
    return {"label": label, "agree": agree, "total": total,
            "disagree": disagree, "note": note}


# Futures contract specs: $ value per 1.0 point of price move.
POINT_VALUE = {"NQ": 20.0, "ES": 50.0, "GOLD": 100.0,   # full-size
               "MNQ": 2.0, "MES": 5.0, "MGC": 10.0}     # micros


def position_size(symbol: str, risk_dollars: float, stop_distance_points: float,
                  proxy: bool = True) -> dict:
    """How many contracts to risk `risk_dollars` given stop distance.

    When proxy=True, levels are ETF-scale, so we only return the $-risk math
    and a clear caveat that contract count needs real futures levels.
    """
    if not risk_dollars or not stop_distance_points or stop_distance_points <= 0:
        return {"note": "Need risk_$ and a positive stop distance."}
    if proxy:
        return {
            "risk_dollars": risk_dollars,
            "note": ("Position size in CONTRACTS requires real futures levels "
                     "(connect Tradovate). On ETF-proxy scale we can't map to "
                     "NQ/ES contracts yet."),
        }
    pv = POINT_VALUE.get(symbol)
    if not pv:
        return {"note": f"No point value for {symbol}."}
    risk_per_contract = stop_distance_points * pv
    contracts = int(risk_dollars // risk_per_contract) if risk_per_contract else 0
    return {
        "risk_dollars": risk_dollars,
        "point_value": pv,
        "stop_points": round(stop_distance_points, 2),
        "risk_per_contract": round(risk_per_contract, 2),
        "suggested_contracts": contracts,
        "actual_risk": round(contracts * risk_per_contract, 2),
    }
