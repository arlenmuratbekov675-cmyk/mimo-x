# Walk-Forward Report — candidate_regime_v1

Generated from /replay/walkforward (lookback=1000, test=100, step=50), FROZEN rule.

## Stability Summary
| Metric | Value |
|---|---|
| Windows evaluated | 17 |
| Mean expectancy | +0.234R |
| Median expectancy | +0.333R |
| Stdev expectancy | 0.31R |
| % positive windows | 64.7% (11/17) |
| Worst window | -0.275R |
| Best window | +0.812R |

## Per-window expectancy (oldest → newest)
| Window | Expectancy |
|---|---|
| W1-W11 (older eras) | choppy, avg ~+0.07R, ~half near zero/negative |
| W12 | +0.42R |
| W13 | +0.53R |
| W14 | +0.64R |
| W15 | +0.42R |
| W16 | +0.37R |
| W17 | +0.81R |

## Conclusion
Era-dependent. NOT a universal edge. Strong and consistent in the CURRENT regime
(last 6 windows all positive, avg ~+0.53R). Must be monitored for regime drift.

## Split test (corroborating)
- 400-bar: train +0.533R / test +0.645R — PASS
- 800-bar: train +0.121R (weak, GOLD negative) / test +0.62R — recent strong, old weak
