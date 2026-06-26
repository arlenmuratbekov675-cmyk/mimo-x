"""MiMo X entrypoint - cache, auth, multi-factor bias, backtest, dashboard."""
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from app.backtest import router as backtest_router
from app.bias import router as bias_router
from app.config import settings
from app.database import Base, engine
from app.datasources import cache_info
from app.history import router as history_router
from app import models  # noqa: F401

app = FastAPI(title=settings.app_name, version="0.8.1")

Base.metadata.create_all(bind=engine)

for r in (bias_router, history_router, backtest_router):
    app.include_router(r, prefix="/v1")
    app.include_router(r)


@app.get("/health")
def health():
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok", "app": settings.app_name, "version": "0.8.1",
        "environment": settings.environment, "database": "ok" if db_ok else "error",
        "auth": "enabled" if settings.api_key else "disabled",
        "cache": cache_info(),
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
def root():
    return {"message": "MiMo X. See /health, /bias, /history, /backtest, /dashboard, /docs."}


_DASHBOARD_HTML = "<!DOCTYPE html>\n<html lang=\"ru\"><head><meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n<title>MiMo X Bias Dashboard</title>\n<style>\n:root{--bg:#0d1117;--card:#161b22;--bd:#30363d;--tx:#e6edf3;--mut:#8b949e;--long:#26a641;--short:#f85149;--neu:#9e9e9e;--acc:#58a6ff}\n*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font-family:-apple-system,Segoe UI,Roboto,sans-serif;padding:16px}\nh1{font-size:20px;margin:0 0 4px}.sub{color:var(--mut);font-size:13px;margin-bottom:16px}\n.regime{display:inline-block;padding:6px 14px;border-radius:20px;font-weight:700;font-size:14px}\n.RISK_ON{background:rgba(38,166,65,.18);color:var(--long)}.RISK_OFF{background:rgba(248,81,73,.18);color:var(--short)}\n.MIXED,.DATA_NOT_READY{background:rgba(158,158,158,.18);color:var(--neu)}\n.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-top:16px}\n.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px}\n.row{display:flex;justify-content:space-between;align-items:center}\n.sym{font-size:18px;font-weight:700}.proxy{color:var(--mut);font-size:12px;font-weight:400}\n.badge{padding:4px 12px;border-radius:8px;font-weight:700;font-size:14px}\n.b-LONG{background:rgba(38,166,65,.18);color:var(--long)}.b-SHORT{background:rgba(248,81,73,.18);color:var(--short)}\n.b-NEUTRAL,.b-DATA_NOT_READY{background:rgba(158,158,158,.18);color:var(--neu)}\n.price{font-size:22px;font-weight:700;margin:8px 0}.chg-up{color:var(--long)}.chg-dn{color:var(--short)}\n.kv{display:flex;justify-content:space-between;font-size:13px;padding:3px 0;border-bottom:1px solid rgba(255,255,255,.04)}\n.kv span:first-child{color:var(--mut)}\n.plan{margin-top:10px;background:rgba(88,166,255,.07);border:1px solid rgba(88,166,255,.2);border-radius:8px;padding:10px}\n.plan h4{margin:0 0 6px;font-size:12px;color:var(--acc);text-transform:uppercase;letter-spacing:.5px}\n.plan .e{color:var(--acc)}.plan .s{color:var(--short)}.plan .t{color:var(--long)}\n.macro{margin-top:16px}.macro .card{padding:12px}\n.footer{margin-top:20px;color:var(--mut);font-size:12px;text-align:center}\n.conf-null{color:var(--mut);font-style:italic}\n.q{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:700;margin-left:6px}\n.q-STRONG{background:rgba(38,166,65,.25);color:var(--long)}.q-MODERATE{background:rgba(88,166,255,.2);color:var(--acc)}\n.q-WEAK{background:rgba(158,158,158,.2);color:var(--neu)}.q-CONFLICTING{background:rgba(248,81,73,.2);color:var(--short)}\n.q-NEUTRAL{background:rgba(158,158,158,.15);color:var(--neu)}\n.warns{margin-top:14px}.warns .w{background:rgba(210,153,34,.12);border:1px solid rgba(210,153,34,.35);border-radius:8px;padding:8px 12px;font-size:12px;color:#e3b341;margin-bottom:6px}\nbutton{background:var(--acc);color:#000;border:0;border-radius:8px;padding:8px 16px;font-weight:600;cursor:pointer}\n</style></head><body>\n<h1>MiMo X Bias Dashboard</h1>\n<div class=\"sub\">Multi-factor analysis | <span id=\"time\">loading...</span> <button onclick=\"load()\">Refresh</button></div>\n<div id=\"regime\"></div>\n<div class=\"grid\" id=\"cards\"></div>\n<div class=\"warns\" id=\"warns\"></div>\n<div class=\"warns\" id=\"calendar\"></div>\n<div class=\"macro\"><h3>Macro and Breadth</h3><div class=\"grid\" id=\"macro\"></div></div>\n<div class=\"footer\">Analytics only. All decisions and orders are manual (Apex rules). Confidence is measured (backtest), never invented.</div>\n<script>\nfunction fmt(n){return n==null?'-':(typeof n==='number'?n.toLocaleString('en-US',{maximumFractionDigits:2}):n)}\nfunction card(k,d){\n var b=d.bias,plan=d.trade_plan,f=d.factors||{},sq=d.signal_quality||{},qL=sq.label||'';\n var chg=d.change_pct,chgC=chg>0?'chg-up':'chg-dn',chgS=chg>0?'+':'';\n var conf=d.confidence==null?'<span class=\"conf-null\">null (collecting history)</span>':d.confidence+'%';\n var tr=f.trend||{};\n var trend=(tr.price_vs_sma20?('price '+tr.price_vs_sma20+' SMA20'):'-')+(tr.sma20_vs_sma50?(' | SMA20 '+tr.sma20_vs_sma50+' SMA50'):'');\n var breadth=f.breadth?('breadth '+(f.breadth.pct_above_sma20!=null?Math.round(f.breadth.pct_above_sma20*100)+'%':'?')):'';\n var vol=d.volatility?d.volatility.regime+' ('+d.volatility.daily_pct+'%/d)':'-';\n var planH=plan?('<div class=\"plan\"><h4>Trade Plan ('+plan.rr+':1 R:R)</h4>'+\n   '<div class=\"kv\"><span>Entry</span><span class=\"e\">'+fmt(plan.entry)+'</span></div>'+\n   '<div class=\"kv\"><span>Stop</span><span class=\"s\">'+fmt(plan.stop)+' (-'+plan.risk_pct+'%)</span></div>'+\n   '<div class=\"kv\"><span>Target</span><span class=\"t\">'+fmt(plan.target)+' (+'+plan.reward_pct+'%)</span></div>'+\n   '<div class=\"kv\"><span>ATR</span><span>'+fmt(plan.atr)+' ('+plan.atr_pct+'%)</span></div></div>'):\n   '<div class=\"plan\"><h4>Trade Plan</h4><div style=\"color:var(--mut);font-size:13px\">No setup (NEUTRAL / no data)</div></div>';\n return '<div class=\"card\"><div class=\"row\"><div><span class=\"sym\">'+k+'</span> <span class=\"proxy\">via '+(d.proxy_symbol||'')+'</span></div>'+\n  '<div><span class=\"badge b-'+b+'\">'+b+'</span>'+(qL?'<span class=\"q q-'+qL+'\">'+qL+'</span>':'')+'</div></div>'+\n  (sq.note?'<div style=\"font-size:11px;color:var(--mut);margin-top:4px\">'+sq.note+'</div>':'')+\n  '<div class=\"price\">'+fmt(d.price)+' <span class=\"'+chgC+'\" style=\"font-size:14px\">'+chgS+fmt(chg)+'%</span></div>'+\n  '<div class=\"kv\"><span>Raw score</span><span>'+(d.raw_score==null?'-':(d.raw_score>0?'+':'')+d.raw_score)+'</span></div>'+\n  '<div class=\"kv\"><span>Confidence</span><span>'+conf+'</span></div>'+\n  '<div class=\"kv\"><span>Trend</span><span>'+trend+'</span></div>'+\n  (breadth?'<div class=\"kv\"><span>Breadth</span><span>'+breadth+'</span></div>':'')+\n  '<div class=\"kv\"><span>Volatility</span><span>'+vol+'</span></div>'+planH+'</div>';\n}\nasync function load(){\n try{\n  var r=await fetch('/bias');var d=await r.json();\n  document.getElementById('time').textContent=new Date().toLocaleString();\n  var feed=(d.sources&&d.sources.price_feed)||'?';\n  var feedTxt=feed==='tradovate'?'Tradovate (real futures)':'ETF proxy (QQQ/SPY/GLD - direction, not exact NQ/ES prices)';\n  document.getElementById('regime').innerHTML='<span class=\"regime '+d.regime+'\">Regime: '+d.regime+'</span> <span style=\"margin-left:10px;font-size:12px;color:var(--mut)\">Feed: '+feedTxt+'</span>';\n  document.getElementById('cards').innerHTML=['NQ','ES','GOLD'].map(k=>card(k,d[k])).join('');\n  var w=d.warnings||[];document.getElementById('warns').innerHTML=w.length?('<h3>Warnings (Apex rules)</h3>'+w.map(x=>'<div class=\"w\">'+x+'</div>').join('')):'';\n  var cal=d.calendar||{};var ev=cal.events||[];\n  document.getElementById('calendar').innerHTML=ev.length?('<h3>Economic Calendar (next 3 days)</h3>'+ev.map(e=>'<div class=\"w\" style=\"background:rgba(88,166,255,.1);border-color:rgba(88,166,255,.3);color:#79c0ff\">'+e.date+' — '+e.event+' ['+e.impact+']</div>').join('')):'';\n  var m=d.macro||{},br=d.breadth||{};\n  function mc(label,o){if(!o)return '';if(o.error)return '<div class=\"card\"><div class=\"row\"><b>'+label+'</b><span class=\"conf-null\">n/a</span></div></div>';\n   var c=o.change>0?'chg-up':'chg-dn';return '<div class=\"card\"><div class=\"row\"><b>'+label+'</b><span class=\"'+c+'\">'+(o.change>0?'+':'')+fmt(o.change)+'</span></div><div class=\"kv\"><span>latest</span><span>'+fmt(o.latest)+'</span></div></div>';}\n  document.getElementById('macro').innerHTML=mc('VIX',m.VIX)+mc('US10Y',m.US10Y)+mc('DXY',m.DXY)+\n   '<div class=\"card\"><div class=\"row\"><b>Breadth</b><span>'+(br.pct_above_sma20!=null?Math.round(br.pct_above_sma20*100)+'%':'-')+'</span></div><div class=\"kv\"><span>above SMA20</span><span>'+(br.above||'?')+'/'+(br.total||'?')+'</span></div></div>';\n }catch(e){document.getElementById('cards').innerHTML='<div class=\"warns\"><div class=\"w\">Load error: '+e+'</div></div>';}\n}\nload();\n</script></body></html>"


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return _DASHBOARD_HTML


@app.get("/calendar")
def calendar_endpoint(days_ahead: int = 7):
    from app import calendar as econ_calendar
    return econ_calendar.upcoming_events(days_ahead=days_ahead)
