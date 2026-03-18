"""
Layer 3: Reversal Blocker
Owner: Alankritha

Prevents chasing spikes. Checks:
1. Did price spike > 2% in last 1-3 candles?
2. Did spread widen abnormally (> 1.5x avg)?
3. Is volume > 3x average?

If ANY triggers → BLOCK entry for 2 cycles.

STUB FILE — Alankritha implements the logic.
"""

import pandas as pd
from config import SPIKE_THRESHOLD, SPREAD_MULTIPLIER, VOLUME_SPIKE_MULTIPLIER


def check_reversal_block(df: pd.DataFrame) -> bool:
    """
    Layer 3: Check if it's safe to enter a trade.

    Args:
        df: DataFrame with OHLCV columns + optional 'spread' column

    Returns:
        True = safe to trade (PASS)
        False = blocked, don't trade (BLOCK)

    TODO (Alankritha):
    - Check if price moved > SPIKE_THRESHOLD (2%) in last 1-3 candles
    - Check if spread > SPREAD_MULTIPLIER (1.5x) of 20-period average spread
    - Check if volume > VOLUME_SPIKE_MULTIPLIER (3x) of 20-period average volume
    - If ANY check triggers, return False
    - Track cooldown state (block for BLOCKER_COOLDOWN_CYCLES after trigger)
    """
    # PLACEHOLDER — returns True (pass) until implemented
    # Remove this and implement the actual logic
    return True
