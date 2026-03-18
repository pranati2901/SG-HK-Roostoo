"""
Layer 5: XGBoost Confirmation
Owner: Pranati

Binary classifier: "Will forward return > fees + threshold?"
Returns probability 0.0 to 1.0.
If probability < 0.65 → NO TRADE.

STUB FILE — Pranati implements the full ML pipeline.
"""

import os
import numpy as np
import pandas as pd
from config import XGBOOST_MIN_PROBABILITY, MODELS_DIR

# Model will be loaded from file once trained
_model = None


def load_model():
    """Load trained XGBoost model from disk."""
    global _model
    model_path = os.path.join(MODELS_DIR, 'xgboost_model.pkl')
    if os.path.exists(model_path):
        import joblib
        _model = joblib.load(model_path)
        return True
    return False


def engineer_features(df: pd.DataFrame) -> dict:
    """
    Calculate all 10 features from candle data.

    TODO (Pranati):
    1. Log returns (1, 3, 5, 10 bars)
    2. ATR/Price (volatility ratio)
    3. RSI(14) + RSI change over 3 bars
    4. MACD histogram value
    5. Bollinger Band %B
    6. Volume ratio (current / 20-bar avg)
    7. Cyclical time encoding (sin/cos of hour)
    8. Rolling autocorrelation
    9. Market breadth (passed in or calculated)
    10. Spread proxy

    Returns:
        dict of feature_name: value
    """
    # PLACEHOLDER — return dummy features until implemented
    return {
        'log_return_1': 0.0,
        'log_return_3': 0.0,
        'log_return_5': 0.0,
        'log_return_10': 0.0,
        'atr_price_ratio': 0.0,
        'rsi_14': 50.0,
        'rsi_change_3': 0.0,
        'macd_hist': 0.0,
        'bb_percent_b': 0.5,
        'volume_ratio': 1.0,
        'hour_sin': 0.0,
        'hour_cos': 1.0,
        'autocorrelation': 0.0,
        'market_breadth': 0.5,
        'spread_proxy': 0.001,
    }


def xgboost_confirm(features_dict: dict) -> float:
    """
    Layer 5: Get XGBoost probability for trade confirmation.

    Args:
        features_dict: dict of feature_name: value (from engineer_features)

    Returns:
        float: probability 0.0 to 1.0
        Returns 1.0 if model not loaded (passthrough until Pranati delivers)
    """
    global _model

    if _model is None:
        if not load_model():
            # Model not trained yet — passthrough (don't block trades)
            return 1.0

    feature_values = np.array([list(features_dict.values())])
    probability = _model.predict_proba(feature_values)[0][1]
    return float(probability)
