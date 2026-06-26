"""Economic calendar - real high-impact events from ForexFactory weekly feed.

FRED was abandoned here: FRED "release dates" are when FRED uploads data to its
own database, NOT when the market-moving event happens. That produced phantom
events (e.g. a fake FOMC). ForexFactory's free weekly JSON gives real event
times + impact ratings - the same source traders read.
"""
from datetime import datetime, timezone

import requests

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (MiMo-X economic calendar)"}


def _parse(dt_str: str):
    # Format: 2026-06-25T08:30:00-04:00
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def upcoming_events(days_ahead: int = 7,
                    countries=("USD",),
                    impacts=("High",)) -> dict:
    try:
        r = requests.get(FF_URL, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return {"events": [], "note": f"calendar source returned {r.status_code}"}
        raw = r.json()
    except Exception as e:
        return {"events": [], "note": f"calendar fetch failed: {e}"}

    now = datetime.now(timezone.utc)
    today_str = now.date().isoformat()
    events = []
    for e in raw:
        if countries and e.get("country") not in countries:
            continue
        if impacts and e.get("impact") not in impacts:
            continue
        dt = _parse(e.get("date", ""))
        if dt is None:
            continue
        d_utc = dt.astimezone(timezone.utc)
        delta_days = (d_utc.date() - now.date()).days
        if delta_days < 0 or delta_days > days_ahead:
            continue
        events.append({
            "date": d_utc.date().isoformat(),
            "time_local": dt.strftime("%H:%M"),
            "datetime": d_utc.isoformat(),
            "event": e.get("title", "?"),
            "impact": e.get("impact", "?").upper(),
            "forecast": e.get("forecast", ""),
            "previous": e.get("previous", ""),
        })
    # Annotate minutes until each event (for time-of-day awareness).
    for e in events:
        ed = _parse(e["datetime"])
        if ed is not None:
            e["minutes_until"] = int((ed.astimezone(timezone.utc) - now).total_seconds() // 60)
        else:
            e["minutes_until"] = None
    events.sort(key=lambda x: x["datetime"])
    note = ("Real high-impact USD events (ForexFactory). Avoid new entries right "
            "before these - news whipsaws stops (Apex: no gambling on news).")
    return {
        "events": events,
        "days_ahead": days_ahead,
        "note": note,
        "has_event_today": any(e["date"] == today_str for e in events),
        "imminent": [e for e in events
                     if e.get("minutes_until") is not None
                     and -15 <= e["minutes_until"] <= 30],
        "source": "forexfactory",
    }
