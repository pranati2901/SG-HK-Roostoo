"""
Layer 4: Multi-Timeframe Filter
Owner: Narhen

Scores 3 timeframes (1H, 4H, Daily):
  +1 = bullish, 0 = neutral, -1 = bearish
Sum >= +2 = PASS (trade allowed)
Sum < +2 = BLOCK
HARD RULE: if 4H is bearish, NEVER buy.
"""

import numpy as np
import pandas as pd
from config import EMA_MID, MACD_FAST, MACD_SLOW, MACD_SIGNAL, EMA_SLOW, TF_MIN_SCORE


def _score_timeframe(df: pd.DataFrame, use_ema50: bool = False) -> int:
    """Score a single timeframe as +1 (bullish), 0 (neutral), -1 (bearish)."""
    if len(df) < EMA_SLOW + 5:
        return 0

    close = df['close']

    if use_ema50:
        # Daily: just check price vs EMA(50)
        ema50 = close.ewm(span=EMA_SLOW, adjust=False).mean().iloc[-1]
        return 1 if close.iloc[-1] > ema50 else -1

    # 1H/4H: EMA slope + MACD direction
    ema = close.ewm(span=EMA_MID, adjust=False).mean()
    ema_slope = ema.iloc[-1] - ema.iloc[-3] if len(ema) >= 3 else 0

    ema_fast = close.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=MACD_SLOW, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()

    macd_above_signal = macd_line.iloc[-1] > signal_line.iloc[-1]

    if ema_slope > 0 and macd_above_signal:
        return 1
    elif ema_slope < 0 and not macd_above_signal:
        return -1
    else:
        return 0


def check_timeframe(df_1h: pd.DataFrame, df_4h: pd.DataFrame,
                    df_daily: pd.DataFrame) -> dict:
    """
    Layer 4: Multi-timeframe filter.

    Args:
        df_1h: 1-hour candle DataFrame
        df_4h: 4-hour candle DataFrame
        df_daily: Daily candle DataFrame

    Returns:
        {
            'pass': bool,        # True if trade is allowed
            'score': int,        # Sum of timeframe scores (-3 to +3)
            'multiplier': float, # 1.0 for +3, 0.5 for +2, 0.0 otherwise
            'scores': dict       # Individual timeframe scores
        }
    """
    score_1h = _score_timeframe(df_1h)
    score_4h = _score_timeframe(df_4h)
    score_daily = _score_timeframe(df_daily, use_ema50=True)

    total = score_1h + score_4h + score_daily

    # Hard rule: never trade against 4H trend
    if score_4h == -1:
        return {
            'pass': False,
            'score': total,
            'multiplier': 0.0,
            'scores': {'1h': score_1h, '4h': score_4h, 'daily': score_daily},
        }

    if total >= 3:
        multiplier = 1.0
    elif total >= TF_MIN_SCORE:
        multiplier = 0.5
    else:
        multiplier = 0.0

    return {
        'pass': total >= TF_MIN_SCORE,
        'score': total,
        'multiplier': multiplier,
        'scores': {'1h': score_1h, '4h': score_4h, 'daily': score_daily},
    }
