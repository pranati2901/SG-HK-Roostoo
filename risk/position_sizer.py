"""
Layer 6: Position Sizing + Risk Management
Owner: Kireeti

Determines how much to trade using:
- Adaptive Quarter-Kelly (self-updates every 20 trades)
- Regime multiplier
- Timeframe multiplier
- Drawdown throttle
- Hard limits
- Emergency kill switch

STUB FILE — Kireeti implements the full logic.
"""

import time
from config import (
    KELLY_FRACTION, KELLY_MIN_POSITION, KELLY_MAX_POSITION,
    MAX_POSITION_PCT, MAX_LOSS_PER_TRADE, RISK_PER_TRADE, MAX_OPEN_ORDERS,
    DRAWDOWN_LEVEL_1, DRAWDOWN_LEVEL_2, DRAWDOWN_LEVEL_3, DRAWDOWN_LEVEL_4,
    DRAWDOWN_KILL, SHARPE_KILL, HALT_HOURS, KILL_HALT_HOURS,
)


def calculate_position(equity: float, regime: str, tf_multiplier: float,
                       xgb_prob: float, trade_history: list) -> dict:
    """
    Layer 6: Calculate position size and check if trade is allowed.

    Args:
        equity: Current portfolio value in USDT
        regime: 'TRENDING' | 'SIDEWAYS' | 'VOLATILE'
        tf_multiplier: From Layer 4 (1.0 or 0.5)
        xgb_prob: From Layer 5 (0.0 to 1.0)
        trade_history: List of past trade P&L percentages (for Kelly)

    Returns:
        {
            'size_usd': float,    # Dollar amount to trade
            'size_btc': float,    # BTC amount (calculated by caller using price)
            'can_trade': bool,    # Whether trade is allowed
            'reason': str,        # Why blocked (if blocked)
        }

    TODO (Kireeti):
    - Implement AdaptiveKelly class (recalculate every 20 trades)
    - Apply regime multiplier (TRENDING=1.0, SIDEWAYS=0.5, VOLATILE=0.1)
    - Apply timeframe multiplier
    - Check drawdown throttle against peak equity
    - Apply hard limits (max 35%, max 1.5% loss per trade)
    - Implement emergency kill switch (drawdown >15% OR Sharpe <-0.5)
    - Clamp Kelly output between 2% and 15%
    """
    # PLACEHOLDER — simple fixed 5% until Kireeti implements
    regime_mult = {'TRENDING': 1.0, 'SIDEWAYS': 0.5, 'VOLATILE': 0.1}.get(regime, 0.5)
    base_pct = 0.05  # 5% default
    final_pct = base_pct * regime_mult * tf_multiplier
    size_usd = equity * min(final_pct, MAX_POSITION_PCT)

    return {
        'size_usd': size_usd,
        'size_btc': 0.0,  # Caller divides by price
        'can_trade': True,
        'reason': 'placeholder_sizing',
    }
