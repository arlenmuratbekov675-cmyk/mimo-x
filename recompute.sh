#!/bin/bash
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
OUT=$(curl -s -X POST http://localhost:8000/backtest/recompute)
echo "$TS recompute $OUT" >> ~/mimo-x/logs/recompute.log
