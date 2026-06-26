#!/bin/bash
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
CODE=$(curl -s -o /tmp/bias_out.json -w "%{http_code}" http://localhost:8000/bias)
REGIME=$(grep -o '"regime":"[^"]*"' /tmp/bias_out.json | head -1)
echo "$TS http=$CODE $REGIME" >> ~/mimo-x/logs/collect.log
