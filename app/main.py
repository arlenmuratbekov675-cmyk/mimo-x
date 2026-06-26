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

app = FastAPI(title=settings.app_name, version="0.10.0")

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
        "status": "ok", "app": settings.app_name, "version": "0.10.0",
        "environment": settings.environment, "database": "ok" if db_ok else "error",
        "auth": "enabled" if settings.api_key else "disabled",
        "cache": cache_info(),
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
def root():
    return {"message": "MiMo X. See /health, /bias, /history, /backtest, /dashboard, /docs."}


_DASHBOARD_HTML = "<!DOCTYPE html>\n<html lang=\"ru\"><head><meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n<title>MiMo X Bias Dashboard</title>\n<style>\n:root{--bg:#0d1117;--card:#161b22;--bd:#30363d;--tx:#e6edf3;--mut:#8b949e;--long:#26a641;--short:#f85149;--neu:#9e9e9e;--acc:#58a6ff}\n*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font-family:-apple-system,Segoe UI,Roboto,sans-serif;padding:16px}\nh1{font-size:20px;margin:0 0 4px}.sub{color:var(--mut);font-size:13px;margin-bottom:16px}\n.regime{display:inline-block;padding:6px 14px;border-radius:20px;font-weight:700;font-size:14px}\n.RISK_ON{background:rgba(38,166,65,.18);color:var(--long)}.RISK_OFF{background:rgba(248,81,73,.18);color:var(--short)}\n.MIXED,.DATA_NOT_READY{background:rgba(158,158,158,.18);color:var(--neu)}\n.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-top:16px}\n.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px}\n.row{display:flex;justify-content:space-between;align-items:center}\n.sym{font-size:18px;font-weight:700}.proxy{color:var(--mut);font-size:12px;font-weight:400}\n.badge{padding:4px 12px;border-radius:8px;font-weight:700;font-size:14px}\n.b-LONG{background:rgba(38,166,65,.18);color:var(--long)}.b-SHORT{background:rgba(248,81,73,.18);color:var(--short)}\n.b-NEUTRAL,.b-DATA_NOT_READY{background:rgba(158,158,158,.18);color:var(--neu)}\n.price{font-size:22px;font-weight:700;margin:8px 0}.chg-up{color:var(--long)}.chg-dn{color:var(--short)}\n.kv{display:flex;justify-content:space-between;font-size:13px;padding:3px 0;border-bottom:1px solid rgba(255,255,255,.04)}\n.kv span:first-child{color:var(--mut)}\n.plan{margin-top:10px;background:rgba(88,166,255,.07);border:1px solid rgba(88,166,255,.2);border-radius:8px;padding:10px}\n.plan h4{margin:0 0 6px;font-size:12px;color:var(--acc);text-transform:uppercase;letter-spacing:.5px}\n.plan .e{color:var(--acc)}.plan .s{color:var(--short)}.plan .t{color:var(--long)}\n.macro{margin-top:16px}.macro .card{padding:12px}\n.footer{margin-top:20px;color:var(--mut);font-size:12px;text-align:center}\n.conf-null{color:var(--mut);font-style:italic}\n.q{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:700;margin-left:6px}\n.q-STRONG{background:rgba(38,166,65,.25);color:var(--long)}.q-MODERATE{background:rgba(88,166,255,.2);color:var(--acc)}\n.q-WEAK{background:rgba(158,158,158,.2);color:var(--neu)}.q-CONFLICTING{background:rgba(248,81,73,.2);color:var(--short)}\n.q-NEUTRAL{background:rgba(158,158,158,.15);color:var(--neu)}\n.warns{margin-top:14px}.warns .w{background:rgba(210,153,34,.12);border:1px solid rgba(210,153,34,.35);border-radius:8px;padding:8px 12px;font-size:12px;color:#e3b341;margin-bottom:6px}\nbutton{background:var(--acc);color:#000;border:0;border-radius:8px;padding:8px 16px;font-weight:600;cursor:pointer}\n</style></head><body>\n<h1>MiMo X Bias Dashboard</h1>\n<div class=\"sub\">Multi-factor analysis | <span id=\"time\">loading...</span> <button onclick=\"load()\">Refresh</button></div>\n<div id=\"health\" style=\"display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:12px 0\"></div><div id=\"regimeMon\"></div><div id=\"confidence\"></div><div id=\"regime\"></div>\n<div class=\"grid\" id=\"cards\"></div>\n<div class=\"warns\" id=\"warns\"></div>\n<div class=\"warns\" id=\"calendar\"></div>\n<div class=\"macro\"><h3>Macro and Breadth</h3><div class=\"grid\" id=\"macro\"></div></div>\n<div class=\"footer\">Analytics only. All decisions and orders are manual (Apex rules). Confidence is measured (backtest), never invented.</div>\n<script>\nfunction fmt(n){return n==null?'-':(typeof n==='number'?n.toLocaleString('en-US',{maximumFractionDigits:2}):n)}\nfunction card(k,d){\n var b=d.bias,plan=d.trade_plan,f=d.factors||{},sq=d.signal_quality||{},qL=sq.label||'';\n var chg=d.change_pct,chgC=chg>0?'chg-up':'chg-dn',chgS=chg>0?'+':'';\n var conf=d.confidence==null?'<span class=\"conf-null\">null (collecting history)</span>':d.confidence+'%';\n var tr=f.trend||{};\n var trend=(tr.price_vs_sma20?('price '+tr.price_vs_sma20+' SMA20'):'-')+(tr.sma20_vs_sma50?(' | SMA20 '+tr.sma20_vs_sma50+' SMA50'):'');\n var breadth=f.breadth?('breadth '+(f.breadth.pct_above_sma20!=null?Math.round(f.breadth.pct_above_sma20*100)+'%':'?')):'';\n var vol=d.volatility?d.volatility.regime+' ('+d.volatility.daily_pct+'%/d)':'-';\n var planH=plan?('<div class=\"plan\"><h4>Trade Plan ('+plan.rr+':1 R:R)</h4>'+\n   '<div class=\"kv\"><span>Entry</span><span class=\"e\">'+fmt(plan.entry)+'</span></div>'+\n   '<div class=\"kv\"><span>Stop</span><span class=\"s\">'+fmt(plan.stop)+' (-'+plan.risk_pct+'%)</span></div>'+\n   '<div class=\"kv\"><span>Target</span><span class=\"t\">'+fmt(plan.target)+' (+'+plan.reward_pct+'%)</span></div>'+\n   '<div class=\"kv\"><span>ATR</span><span>'+fmt(plan.atr)+' ('+plan.atr_pct+'%)</span></div></div>'):\n   '<div class=\"plan\"><h4>Trade Plan</h4><div style=\"color:var(--mut);font-size:13px\">No setup (NEUTRAL / no data)</div></div>';\n return '<div class=\"card\"><div class=\"row\"><div><span class=\"sym\">'+k+'</span> <span class=\"proxy\">via '+(d.proxy_symbol||'')+'</span></div>'+\n  '<div><span class=\"badge b-'+b+'\">'+b+'</span>'+(qL?'<span class=\"q q-'+qL+'\">'+qL+'</span>':'')+'</div></div>'+\n  (sq.note?'<div style=\"font-size:11px;color:var(--mut);margin-top:4px\">'+sq.note+'</div>':'')+\n  '<div class=\"price\">'+fmt(d.price)+' <span class=\"'+chgC+'\" style=\"font-size:14px\">'+chgS+fmt(chg)+'%</span></div>'+\n  '<div class=\"kv\"><span>Raw score</span><span>'+(d.raw_score==null?'-':(d.raw_score>0?'+':'')+d.raw_score)+'</span></div>'+\n  '<div class=\"kv\"><span>Confidence</span><span>'+conf+'</span></div>'+\n  '<div class=\"kv\"><span>Trend</span><span>'+trend+'</span></div>'+\n  (breadth?'<div class=\"kv\"><span>Breadth</span><span>'+breadth+'</span></div>':'')+\n  '<div class=\"kv\"><span>Volatility</span><span>'+vol+'</span></div>'+planH+'</div>';\n}\nasync function load(){\n try{\n  var r=await fetch('/bias');var d=await r.json();\n  document.getElementById('time').textContent=new Date().toLocaleString();\n  var feed=(d.sources&&d.sources.price_feed)||'?';\n  var feedTxt=feed==='tradovate'?'Tradovate (real futures)':'ETF proxy (QQQ/SPY/GLD - direction, not exact NQ/ES prices)';\n  document.getElementById('regime').innerHTML='<span class=\"regime '+d.regime+'\">Regime: '+d.regime+'</span> <span style=\"margin-left:10px;font-size:12px;color:var(--mut)\">Feed: '+feedTxt+'</span>';\n  document.getElementById('cards').innerHTML=['NQ','ES','GOLD'].map(k=>card(k,d[k])).join('');\n  var w=d.warnings||[];document.getElementById('warns').innerHTML=w.length?('<h3>Warnings (Apex rules)</h3>'+w.map(x=>'<div class=\"w\">'+x+'</div>').join('')):'';\n  var cal=d.calendar||{};var ev=cal.events||[];\n  document.getElementById('calendar').innerHTML=ev.length?('<h3>Economic Calendar (next 3 days)</h3>'+ev.map(e=>'<div class=\"w\" style=\"background:rgba(88,166,255,.1);border-color:rgba(88,166,255,.3);color:#79c0ff\">'+e.date+' — '+e.event+' ['+e.impact+']</div>').join('')):'';\n  var m=d.macro||{},br=d.breadth||{};\n  function mc(label,o){if(!o)return '';if(o.error)return '<div class=\"card\"><div class=\"row\"><b>'+label+'</b><span class=\"conf-null\">n/a</span></div></div>';\n   var c=o.change>0?'chg-up':'chg-dn';return '<div class=\"card\"><div class=\"row\"><b>'+label+'</b><span class=\"'+c+'\">'+(o.change>0?'+':'')+fmt(o.change)+'</span></div><div class=\"kv\"><span>latest</span><span>'+fmt(o.latest)+'</span></div></div>';}\n  document.getElementById('macro').innerHTML=mc('VIX',m.VIX)+mc('US10Y',m.US10Y)+mc('DXY',m.DXY)+\n   '<div class=\"card\"><div class=\"row\"><b>Breadth</b><span>'+(br.pct_above_sma20!=null?Math.round(br.pct_above_sma20*100)+'%':'-')+'</span></div><div class=\"kv\"><span>above SMA20</span><span>'+(br.above||'?')+'/'+(br.total||'?')+'</span></div></div>';\n }catch(e){document.getElementById('cards').innerHTML='<div class=\"warns\"><div class=\"w\">Load error: '+e+'</div></div>';}\n}\nfunction hcell(label,val,sub){return \"<div class=\\\"card\\\" style=\\\"text-align:center\\\"><div style=\\\"color:#9aa;font-size:12px\\\">\"+label+\"</div><div style=\\\"font-size:24px;font-weight:800;margin:4px 0\\\">\"+val+\"</div><div style=\\\"color:#9aa;font-size:11px\\\">\"+(sub||\"\")+\"</div></div>\";}\nfunction loadHealth(){fetch(\"/dashboard/health\").then(r=>r.json()).then(h=>{var sim=h.regime_similarity==null?\"-\":h.regime_similarity+\"%\";var fc=(h.forward_trades||0)+\" / \"+(h.forward_target||100);var pnl=(h.paper_pnl_r>0?\"+\":\"\")+(h.paper_pnl_r||0)+\"R\";var rs=h.research_status||\"-\";document.getElementById(\"health\").innerHTML=hcell(\"Research Status\",(rs==\"FROZEN\"?\"\\uD83D\\uDD12 \":\"\")+rs,h.rule)+hcell(\"Forward Trades\",fc,\"target \"+(h.forward_target||100))+hcell(\"Current Regime\",sim,\"validated \"+(h.validated_range||\"\"))+hcell(\"Paper PnL\",pnl,h.forward_logged+\" signals logged\");}).catch(e=>{});}\nfunction loadRegimeMon(){fetch(\"/regime\").then(r=>r.json()).then(m=>{var sim=m.similarity_pct;var st=m.status||\"\";var color=st==\"MATCHED\"?\"#2ecc71\":(st==\"DRIFTING\"?\"#f1c40f\":\"#e74c3c\");var dot=st==\"MATCHED\"?\"\\uD83D\\uDFE2\":(st==\"DRIFTING\"?\"\\uD83D\\uDFE1\":\"\\uD83D\\uDD34\");fetch(\"/regime/history?limit=40\").then(r=>r.json()).then(hh=>{var hist=(hh.history||[]);var spark=\"\";if(hist.length){var mn=Math.min.apply(null,hist.map(x=>x.similarity));var mx=Math.max.apply(null,hist.map(x=>x.similarity));var rng=(mx-mn)||1;spark=hist.map(x=>{var hgt=8+34*((x.similarity-mn)/rng);return \"<span style=\\\"display:inline-block;width:6px;height:\"+hgt.toFixed(0)+\"px;background:\"+color+\";margin-right:2px;vertical-align:bottom;opacity:.8\\\"></span>\";}).join(\"\");}document.getElementById(\"regimeMon\").innerHTML=\"<div class=\\\"card\\\" style=\\\"border-left:4px solid \"+color+\"\\\"><div class=\\\"row\\\"><span class=\\\"sym\\\">\"+dot+\" Regime Monitor</span><span style=\\\"font-size:22px;font-weight:800;color:\"+color+\"\\\">\"+sim+\"%</span></div>\"+\"<div class=\\\"kv\\\"><span>Status</span><span style=\\\"color:\"+color+\";font-weight:700\\\">\"+st+\"</span></div>\"+\"<div class=\\\"kv\\\"><span>Validated range</span><span>65-100%</span></div>\"+\"<div style=\\\"margin:8px 0;color:#9aa;font-size:12px\\\">\"+m.recommendation+\"</div>\"+(spark?\"<div style=\\\"margin-top:8px\\\"><div style=\\\"color:#9aa;font-size:11px;margin-bottom:4px\\\">Similarity history</div>\"+spark+\"</div>\":\"\")+\"</div>\";}).catch(e=>{});}).catch(e=>{});}\nfunction loadConfidence(){fetch(\"/forward/collect?dry_run=true\").then(r=>r.json()).then(d=>{var rows=d.rows||[];if(!rows.length){document.getElementById(\"confidence\").innerHTML=\"\";return;}var html=\"<h3>Confidence Monitor</h3><div class=\\\"grid\\\">\";rows.forEach(r=>{var c=r.confidence_pct;var col=c>=70?\"#2ecc71\":(c>=60?\"#f1c40f\":\"#e74c3c\");var rec=r.would_trade?\"EXECUTE\":\"SKIP\";var recCol=r.would_trade?\"#2ecc71\":\"#e74c3c\";var reasons=(r.reasons||[]).map(x=>{var ok=x.indexOf(\"PASS\")==0;var bad=x.indexOf(\"FAIL\")==0;var ic=ok?\"\\u2714\":(bad?\"\\u2718\":\"~\");var t=x.replace(/^(PASS|FAIL|~)\\s?/,\"\");return \"<div style=\\\"font-size:12px;color:\"+(ok?\"#2ecc71\":(bad?\"#e74c3c\":\"#f1c40f\"))+\"\\\">\"+ic+\" \"+t+\"</div>\";}).join(\"\");html+=\"<div class=\\\"card\\\" style=\\\"border-top:3px solid \"+col+\"\\\"><div class=\\\"row\\\"><span class=\\\"sym\\\">\"+r.bias+\" \"+r.symbol+\"</span><span style=\\\"font-size:22px;font-weight:800;color:\"+col+\"\\\">\"+c+\"%</span></div>\"+reasons+\"<div class=\\\"kv\\\" style=\\\"margin-top:8px\\\"><span>Recommendation</span><span style=\\\"font-weight:800;color:\"+recCol+\"\\\">\"+rec+\"</span></div></div>\";});html+=\"</div>\";document.getElementById(\"confidence\").innerHTML=html;}).catch(e=>{});}\nfunction loadExtras(){loadHealth();loadRegimeMon();loadConfidence();}\nloadExtras();setInterval(loadExtras,300000);\nload();\n</script></body></html>"


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    try:
        from app.regime_monitor import log_similarity_daily
        log_similarity_daily()  # display-only history accrual
    except Exception:
        pass
    return _DASHBOARD_HTML


@app.get("/digest/preview")
def digest_preview_endpoint():
    """Build the daily digest WITHOUT sending (display-only preview)."""
    from app.telegram_digest import build_digest
    return build_digest()


@app.post("/digest/send")
def digest_send_endpoint():
    """Build and send the daily Telegram digest."""
    from app.telegram_digest import send_daily_digest
    return send_daily_digest()


@app.get("/research/confidence")
def research_confidence_endpoint():
    from app.telegram_digest import build_digest
    return build_digest().get("research_confidence")


@app.get("/regime/history")
def regime_history_endpoint(limit: int = 60):
    from app.regime_monitor import similarity_history
    return {"history": similarity_history(limit=limit)}


@app.get("/dashboard/health")
def dashboard_health_endpoint():
    """Aggregate project-status header (display-only)."""
    import os, json as _j
    out = {"research_status": "FROZEN", "rule": "candidate_regime_v1",
           "validated_range": "65-100%"}
    try:
        from app.regime_monitor import regime_similarity
        out["regime_similarity"] = regime_similarity().get("similarity_pct")
    except Exception:
        out["regime_similarity"] = None
    # forward trades + paper PnL
    decided = 0; logged = 0; total_r = 0.0
    log = os.getenv("PAPER_LOG_FILE", "/code/data/forward_paper.jsonl")
    if os.path.exists(log):
        with open(log) as f:
            for line in f:
                try:
                    r = _j.loads(line)
                except Exception:
                    continue
                logged += 1
                if r.get("r_multiple") is not None:
                    decided += 1; total_r += r["r_multiple"]
    out["forward_trades"] = decided
    out["forward_target"] = 100
    out["forward_logged"] = logged
    out["paper_pnl_r"] = round(total_r, 2) if decided else 0.0
    return out


from app.execution.callbacks import router as ctrader_router
from app.execution.orchestrator import get_orchestrator
app.include_router(ctrader_router)


@app.get("/execution/status")
def execution_status():
    return get_orchestrator().status()


@app.post("/execution/paper-test")
def execution_paper_test():
    """Dry-run: pull current bias and paper-execute each actionable signal."""
    from app.bias import get_bias
    data = get_bias()
    orc = get_orchestrator()
    out = []
    for ib in (data.NQ, data.ES, data.GOLD):
        tp = ib.trade_plan or {}
        if ib.bias not in ("LONG", "SHORT") or not tp.get("entry"):
            continue
        res = orc.execute_signal(
            ib.symbol, ib.bias, tp.get("entry"), tp.get("stop"), tp.get("target"))
        out.append({"symbol": ib.symbol, "bias": ib.bias, "result": res})
    return {"executed": out, "status": orc.status()}


@app.get("/regime")
def regime_endpoint():
    from app.regime_monitor import regime_similarity
    return regime_similarity()


@app.get("/forward/collect")
def forward_collect_endpoint(dry_run: bool = False):
    from app.forward_paper import collect
    return collect(dry_run=dry_run)


@app.get("/forward/stats")
def forward_stats_endpoint():
    from app.forward_paper import stats
    return stats()


@app.get("/replay/walkforward")
def replay_wf_endpoint(lookback: int = 1000, test_size: int = 100, step: int = 50):
    """Rolling walk-forward of candidate_regime_v1 across market eras."""
    from app.replay import run_walkforward
    return run_walkforward(lookback=lookback, test_size=test_size, step=step)


@app.get("/replay/split")
def replay_split_endpoint(lookback: int = 400):
    """Out-of-sample split test of the FROZEN regime-aware rule."""
    from app.replay import run_split
    return run_split(lookback=lookback)


@app.get("/replay")
def replay_endpoint(lookback: int = 400):
    """Walk-forward backtest of the trend+volatility core. Real stats, no money."""
    from app.replay import run_replay
    return run_replay(lookback=lookback)


@app.get("/calendar")
def calendar_endpoint(days_ahead: int = 7):
    from app import calendar as econ_calendar
    return econ_calendar.upcoming_events(days_ahead=days_ahead)