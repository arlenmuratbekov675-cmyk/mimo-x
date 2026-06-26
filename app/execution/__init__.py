"""MiMo X execution package.

Modular by design (your architecture review):
    config      - mode flags, firm compliance guards
    account     - account state snapshot
    risk        - position sizing + FTMO loss-limit guards
    orders      - order lifecycle
    positions   - open position tracking
    oauth       - cTrader OAuth token exchange (KYC-gated)
    bridge      - broker adapter (paper now, cTrader later) - swappable
    orchestrator- thin glue tying a bias signal -> risk -> bridge

Nothing here trades real money until: app is KYC-Active, EXECUTION_ENABLED=true,
EXECUTION_MODE=live, and the firm permits automation (FTMO only).
"""
from app.execution.orchestrator import Orchestrator, get_orchestrator  # noqa: F401
