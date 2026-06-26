# Regression Suite — PLANNED (build AFTER current experiment completes)

Before ANY future change to MiMo is accepted, it must automatically pass:

1. Replay (baseline OHLC backtest)
2. Walk-forward (rolling windows across eras)
3. Comparison against baseline (trend+vol core)
4. Comparison against candidate_regime_v1

## Acceptance rule
A new version REPLACES the current one ONLY if it is better by PRE-DEFINED
criteria (expectancy, drawdown, stability across windows). Otherwise rejected.

## Purpose
Protect the project from accidental strategy degradation. No change ships on
intuition — every change must prove itself against the frozen reference.

Status: NOT built yet. Planned for after the 100-200 forward-trade experiment.
