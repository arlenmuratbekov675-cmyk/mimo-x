# MiMo X — Strategy Assumptions & Limitations

## Philosophy
> We are NOT searching for a perfect, all-weather strategy.
> We are building a strategy that KNOWS WHEN IT STOPS WORKING.

"Edge is real now, but regime-dependent." — the project's guiding truth.

## candidate_regime_v1 (EXPERIMENTAL — NOT a proven law)
Rule (FROZEN — do not change until 100-200 forward paper trades collected):
- NQ / ES : trade ONLY in RISK_ON or RISK_OFF regimes (skip NEUTRAL)
- GOLD    : trade ONLY in NEUTRAL regime (skip RISK_ON / RISK_OFF)

Rationale: equities trend with risk sentiment; gold's drivers (real rates, DXY,
Fed expectations) make it behave inversely — it performs in the chop that hurts
equities.

## Regime definition
- SPY vs SMA50  → broad equity direction
- VIX (FRED VIXCLS) vs SMA20 → fear level
- RISK_ON  = SPY up  + VIX calm
- RISK_OFF = SPY down + VIX elevated
- NEUTRAL  = mixed

## What is PROVEN
- Recent out-of-sample (400 & 800 bar splits): +0.62 to +0.645R, maxDD -3.5/-4R. PASS.

## What is NOT proven (honest limitations)
- LONG-HISTORY ROBUSTNESS: rolling walk-forward (17 windows) shows era-dependence.
  - Mean expectancy across all eras: +0.234R (modest)
  - Stdev: 0.31R (high) — only 64.7% of windows positive
  - Older eras choppy (~+0.07R avg); recent 6 windows strong (~+0.53R avg, all positive)
- Therefore: edge is strong in the CURRENT regime, weak/absent in some past eras.
- Small samples per symbol/regime (some < 25 trades) — statistically noisy.
- TIMEOUT trades use optimistic mark-to-market; trust DECIDED win rate.
- Macro (DXY/US10Y) not yet reconstructed in replay for GOLD.
- Paper fills are simulated — real broker behavior (slippage, stops, reconnect) UNTESTED.

## Hard rule going forward
DO NOT modify trading logic until >=100 (ideally 200) real forward paper trades
are collected. Changing filters after every idea = never knowing if anything works.

## Promotion path (each stage must pass before the next)
Rolling Walk-Forward [DONE: era-dependent] →
Forward Paper (100-200 trades) →
Demo FTMO →
Small Live →
Full Live
