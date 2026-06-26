# FREEZE RULES — Observation Phase

Until 100 forward paper trades are collected:

## FORBIDDEN
- New filters
- New indicators
- New strategies
- Any change to trading logic, thresholds, weights, risk manager, entry criteria

## ALLOWED
- Bug fixes
- UI improvements
- Logging improvements
- Monitoring improvements

## Rationale
The biggest risk now is adding features instead of collecting honest data.
Changing logic mid-collection invalidates the statistics. Discipline > features.

> Don't accelerate. The most valuable thing in the coming weeks is accumulating
> honest statistics WITHOUT touching trading logic.

## Research Milestones (data-triggered, not calendar-triggered)
- 25 trades  → brief check
- 50 trades  → stability check
- 100 trades → full statistical analysis
- 200 trades → decision: continue paper / move to demo / revisit hypothesis
