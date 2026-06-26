"""Telegram daily digest - RESEARCH MONITORING only (not a trading terminal).

Design rules (deliberate):
- ONE report per day after session close. No per-trade pings.
- Informative, not action-prompting. Logic stays FROZEN.
- Includes Research Confidence: an objective, predefined readiness score.
"""
from __future__ import annotations
import json, os
from datetime import date, datetime, timezone
from urllib import request as _rq, parse as _ps

PAPER_LOG = os.getenv("PAPER_LOG_FILE", "/code/data/forward_paper.jsonl")
SIM_LOG = os.getenv("SIM_LOG_FILE", "/code/data/regime_similarity.jsonl")
FORWARD_TARGET = int(os.getenv("FORWARD_TARGET", "100"))


def _read_jsonl(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path) as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def research_confidence(decided, expectancy, sim_status):
    """Objective readiness score 0-100 from PREDEFINED criteria (not opinion).

    Components:
      data volume   (0-50): decided trades vs target
      edge sign     (0-30): expectancy > 0 and meaningful
      regime match  (0-20): current regime within validated range
    Score only turns 'green' (>=80) when enough data AND positive edge AND matched.
    """
    data_pts = min(50, round(50 * decided / FORWARD_TARGET)) if FORWARD_TARGET else 0
    if expectancy is None:
        edge_pts = 0
    elif expectancy >= 0.3:
        edge_pts = 30
    elif expectancy > 0:
        edge_pts = round(30 * expectancy / 0.3)
    else:
        edge_pts = 0
    regime_pts = {"MATCHED": 20, "DRIFTING": 10}.get(sim_status, 0)
    total = data_pts + edge_pts + regime_pts
    if total >= 80:
        rec = "Criteria met - statistical review for demo."
    elif decided < FORWARD_TARGET:
        rec = "Continue collecting."
    else:
        rec = "Data complete - review edge before demo."
    return {"score": total, "data_pts": data_pts, "edge_pts": edge_pts,
            "regime_pts": regime_pts, "data_collected_pct": round(100 * decided / FORWARD_TARGET) if FORWARD_TARGET else 0,
            "recommendation": rec}


def build_digest():
    from app.regime_monitor import regime_similarity
    rows = _read_jsonl(PAPER_LOG)
    today = date.today().isoformat()
    todays = [r for r in rows if (r.get("ts") or "").startswith(today)]
    decided = [r for r in rows if r.get("r_multiple") is not None]
    decided_today = [r for r in todays if r.get("r_multiple") is not None]
    by_sym = {}
    for r in todays:
        by_sym[r["symbol"]] = by_sym.get(r["symbol"], 0) + 1
    pnl_today = round(sum(r["r_multiple"] for r in decided_today), 2)
    pnl_total = round(sum(r["r_multiple"] for r in decided), 2)
    exp = round(pnl_total / len(decided), 3) if decided else None
    conf_buckets = {"high": 0, "med": 0, "low": 0}
    for r in todays:
        c = r.get("confidence_pct") or 0
        conf_buckets["high" if c >= 70 else ("med" if c >= 60 else "low")] += 1

    mon = regime_similarity()
    sim = mon.get("similarity_pct"); status = mon.get("status")

    # similarity drift detection (display alert only)
    sims = _read_jsonl(SIM_LOG)
    alert = None
    if len(sims) >= 2 and sim is not None:
        prev = sims[-2].get("similarity")
        if prev is not None and prev >= 65 and sim < 65:
            alert = ("Regime similarity " + str(prev) + "% -> " + str(sim) +
                     "%\nBelow validated range.\nNo action taken.\nRecommendation: continue paper mode.")
    if len(decided) >= FORWARD_TARGET and (len(decided) - len(decided_today)) < FORWARD_TARGET:
        alert = (str(FORWARD_TARGET) + " trades reached.\nStatistical review recommended.\n"
                 "Trading logic remains frozen.")

    rc = research_confidence(len(decided), exp, status)

    lines = []
    lines.append("\U0001F4CA *MiMo Daily*")
    lines.append("")
    lines.append("*Research*")
    lines.append("\U0001F512 candidate\\_regime\\_v1 (FROZEN)")
    lines.append("")
    lines.append("*Forward*")
    lines.append(str(len(decided)) + " / " + str(FORWARD_TARGET) + " trades")
    lines.append("")
    lines.append("*Today's signals*")
    for s in ("NQ", "ES", "GOLD"):
        lines.append(s + ": " + str(by_sym.get(s, 0)))
    lines.append("")
    lines.append("*Paper PnL*")
    lines.append(("+" if pnl_today >= 0 else "") + str(pnl_today) + "R today")
    lines.append(("+" if pnl_total >= 0 else "") + str(pnl_total) + "R total")
    lines.append("")
    lines.append("*Regime*")
    lines.append("Similarity: " + (str(sim) + "%" if sim is not None else "-"))
    lines.append("Status: " + str(status))
    lines.append("")
    lines.append("*Confidence (today)*")
    lines.append("High: " + str(conf_buckets["high"]))
    lines.append("Medium: " + str(conf_buckets["med"]))
    lines.append("Low: " + str(conf_buckets["low"]))
    lines.append("")
    lines.append("*Research Confidence*")
    lines.append(str(rc["score"]) + " / 100")
    lines.append("Data collected: " + str(rc["data_collected_pct"]) + "%")
    lines.append("Recommendation: " + rc["recommendation"])
    lines.append("")
    lines.append("*Warnings*")
    lines.append("\u26A0 " + alert.replace("\n", " ") if alert else "None")
    return {"text": "\n".join(lines), "alert": alert, "research_confidence": rc,
            "decided": len(decided), "similarity": sim, "status": status}


def send_telegram(text):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return {"sent": False, "reason": "TELEGRAM_BOT_TOKEN/CHAT_ID not set"}
    url = "https://api.telegram.org/bot" + token + "/sendMessage"
    data = _ps.urlencode({"chat_id": chat, "text": text, "parse_mode": "Markdown"}).encode()
    try:
        with _rq.urlopen(_rq.Request(url, data=data), timeout=15) as r:
            return {"sent": r.status == 200}
    except Exception as e:
        return {"sent": False, "reason": str(e)}


MILESTONES = [25, 50, 100, 200]
_MILESTONE_FILE = os.getenv("MILESTONE_FILE", "/code/data/milestones.json")


def _milestone_seen():
    if os.path.exists(_MILESTONE_FILE):
        try:
            return set(json.load(open(_MILESTONE_FILE)))
        except Exception:
            return set()
    return set()


def _milestone_save(seen):
    os.makedirs(os.path.dirname(_MILESTONE_FILE), exist_ok=True)
    json.dump(sorted(seen), open(_MILESTONE_FILE, "w"))


def check_milestones():
    """Fire a one-time report when decided trades cross 25/50/100/200.

    Data-triggered, NOT calendar-triggered. Monitoring only - logic stays FROZEN.
    """
    rows = _read_jsonl(PAPER_LOG)
    decided = [r for r in rows if r.get("r_multiple") is not None]
    n = len(decided)
    seen = _milestone_seen()
    fired = [m for m in MILESTONES if n >= m and m not in seen]
    if not fired:
        return {"fired": [], "decided": n}
    m = max(fired)
    rs = [r["r_multiple"] for r in decided]
    exp = round(sum(rs) / len(rs), 3) if rs else None
    wins = sum(1 for x in rs if x > 0)
    wr = round(100 * wins / len(rs)) if rs else 0
    by = {}
    for r in decided:
        by.setdefault(r["symbol"], []).append(r["r_multiple"])
    depth = {25: "Brief check.", 50: "Stability check.",
             100: "Full statistical analysis.",
             200: "Decision point: continue paper / demo / revisit hypothesis."}[m]
    lines = ["\U0001F3AF *Research Milestone: " + str(m) + " trades*", "",
             "Depth: " + depth, "",
             "Expectancy: " + (str(exp) + "R" if exp is not None else "-"),
             "Win rate: " + str(wr) + "%", "",
             "*By symbol*"]
    for s in ("NQ", "ES", "GOLD"):
        v = by.get(s)
        if v:
            lines.append(s + ": " + str(round(sum(v) / len(v), 3)) + "R (" + str(len(v)) + ")")
    lines += ["", "\U0001F512 Trading logic remains FROZEN.",
              "No changes - data only."]
    res = send_telegram("\n".join(lines))
    for m2 in fired:
        seen.add(m2)
    _milestone_save(seen)
    return {"fired": fired, "decided": n, "telegram": res}


def send_daily_digest():
    d = build_digest()
    res = send_telegram(d["text"])
    ms = check_milestones()  # data-triggered, fires once per threshold
    return {"digest": d, "telegram": res, "milestone": ms}