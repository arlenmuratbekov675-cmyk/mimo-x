# \uD83D\uDEAB DO NOT IMPLEMENT ANY ROADMAP ITEM UNTIL DECISION GATE IS PASSED.
# ("MessageBus doesn't change strategy" / "let's quickly add Nautilus" = NO. Frozen.)

# MiMo X — Roadmap (POST-experiment only)

> DO NOTHING here until >=100-200 forward paper trades are collected.
> This is a notes file. Editor stays closed. Logic stays FROZEN.

## Phase: AFTER 25 trades
- First real-data review (expectancy / regime / degradation check)

## Phase: AFTER 100-200 trades + Decision Gate passed
### Architecture references (study, do NOT copy code)
- NautilusTrader — PRIMARY architecture reference
  - [TOP] MessageBus (common/) — decouple bias->risk->execution via event bus
  - [TOP] Backtest = Live parity (backtest/ <-> live/) — single Strategy class,
          same code in replay and prod (kills backtest/prod divergence)
  - RiskEngine as a gate BEFORE ExecutionEngine
  - Separate Portfolio (exposure) / Accounting (margin,P&L) / Cache
  - Strategy isolated in trading/ (logic only reacts to events)
- pysystemtrade — risk/position-sizing reference (vol targeting, overlays)
  - DEFERRED: review only AFTER 25 trades. Do not touch risk layer before that.
- qlib — research platform + feature store reference

### Future scaling (only after edge proven)
- Research Archive (version results per hypothesis, not just code)
- Decision Gate (all criteria pass: trades>=100, exp>=+0.3R, PF>=1.3, DD<=6R,
  no critical regime drift, no execution failures)
- Regression Suite (replay+walk-forward vs baseline & candidate_regime_v1)
- CUA fleet (parallel v1/v2/v3 testing) — scaling phase only

## RULE
Value now = new forward data. NOT new architecture research.