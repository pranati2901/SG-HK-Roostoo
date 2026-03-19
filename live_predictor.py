import pandas as pd
import numpy as np
import joblib
import ta
import warnings
warnings.filterwarnings('ignore')

# ================================================
# LOAD THE TRAINED MODEL (done once at startup)
# ================================================
print("Loading XGBoost model...")
model = joblib.load('xgboost_model.pkl')
feature_columns = joblib.load('feature_columns.pkl')
print("Model loaded and ready!")

# ================================================
# FEATURE CALCULATOR
# Same logic as feature_engineer.py
# But takes live price history instead of CSV
# ================================================
def calculate_live_features(price_history, breadth=0.5, spread_proxy=0.001):
    """
    price_history = list of dicts from your bot's memory
    Each dict: {'timestamp': ..., 'open': ..., 'high': ..., 
                'low': ..., 'close': ..., 'volume': ...}
    
    breadth = from Roostoo /v3/ticker (% coins rising)
    spread_proxy = (MinAsk - MaxBid) / LastPrice from Roostoo
    
    Returns: dict of features OR None if not enough data
    """
    
    # Need at least 50 candles for indicators to work
    if len(price_history) < 50:
        print(f"Not enough data yet: {len(price_history)}/50 candles")
        return None
    
    # Convert to DataFrame
    df = pd.DataFrame(price_history)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Sort by time just in case
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # ================================================
    # Calculate all features (same as feature_engineer.py)
    # ================================================
    
    # Feature 1: Log Returns
    df['log_return_1']  = np.log(df['close'] / df['close'].shift(1))
    df['log_return_3']  = np.log(df['close'] / df['close'].shift(3))
    df['log_return_5']  = np.log(df['close'] / df['close'].shift(5))
    df['log_return_10'] = np.log(df['close'] / df['close'].shift(10))
    
    # Feature 2: ATR Ratio
    atr = ta.volatility.AverageTrueRange(
        high=df['high'], low=df['low'], close=df['close'], window=14
    )
    df['atr'] = atr.average_true_range()
    df['atr_ratio'] = df['atr'] / df['close']
    
    # Feature 3: RSI + RSI Change
    rsi = ta.momentum.RSIIndicator(close=df['close'], window=14)
    df['rsi'] = rsi.rsi()
    df['rsi_change'] = df['rsi'] - df['rsi'].shift(3)
    
    # Feature 4: MACD Histogram
    macd = ta.trend.MACD(
        close=df['close'], 
        window_slow=26, window_fast=12, window_sign=9
    )
    df['macd_histogram'] = macd.macd_diff()
    
    # Feature 5: Bollinger Band %B
    bb = ta.volatility.BollingerBands(
        close=df['close'], window=20, window_dev=2
    )
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_percent_b'] = (
        (df['close'] - df['bb_lower']) / 
        (df['bb_upper'] - df['bb_lower'])
    )
    
    # Feature 6: Volume Ratio
    df['volume_ma20'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma20']
    
    # Feature 7: Time Encoding
    df['hour'] = df['timestamp'].dt.hour
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    
    # Feature 8: Autocorrelation
    df['autocorr'] = df['log_return_1'].rolling(window=20).apply(
        lambda x: pd.Series(x).autocorr(lag=1), raw=False
    )
    
    # Features 9 & 10: Live values from Roostoo
    df['breadth'] = breadth
    df['spread_proxy'] = spread_proxy
    
    # Get the LAST row (most recent candle = current moment)
    df = df.dropna()
    
    if len(df) == 0:
        print("Not enough data after dropping NaN")
        return None
    
    latest = df.iloc[-1]
    
    # Build feature dict
    features = {col: latest[col] for col in feature_columns}
    
    return features

# ================================================
# MAIN PREDICTION FUNCTION
# This is what your teammates call from their bot
# ================================================
def get_xgboost_signal(price_history, breadth=0.5, spread_proxy=0.001, threshold=0.65):
    """
    Main function your teammates call every 60 seconds
    
    Returns:
        'BUY'  if probability >= threshold
        'SKIP' if probability < threshold
        'WAIT' if not enough data yet
    """
    
    # Calculate features
    features = calculate_live_features(price_history, breadth, spread_proxy)
    
    if features is None:
        return 'WAIT', 0.0
    
    # Convert to DataFrame (model expects DataFrame)
    X = pd.DataFrame([features])[feature_columns]
    
    # Get probability from model
    probability = model.predict_proba(X)[0][1]
    
    # Apply threshold
    if probability >= threshold:
        decision = 'BUY'
    else:
        decision = 'SKIP'
    
    print(f"XGBoost probability: {probability:.3f} -> {decision}")
    
    return decision, probability

# ================================================
# TEST WITH FAKE DATA
# Simulates what happens when bot calls this live
# ================================================
if __name__ == "__main__":
    print("\nTesting live predictor with fake data...")
    
    # Simulate 100 candles of price history
    # In real bot this comes from stored price history
    import random
    
    fake_history = []
    base_price = 85000
    
    for i in range(100):
        # Random walk price simulation
        change = random.uniform(-0.002, 0.002)
        base_price = base_price * (1 + change)
        
        fake_history.append({
            'timestamp': pd.Timestamp.now() - pd.Timedelta(minutes=15*(100-i)),
            'open':   base_price * random.uniform(0.999, 1.001),
            'high':   base_price * random.uniform(1.000, 1.003),
            'low':    base_price * random.uniform(0.997, 1.000),
            'close':  base_price,
            'volume': random.uniform(100, 500)
        })
    
    # Test the prediction
    # breadth = 0.55 means 55% of coins are rising
    # spread_proxy = 0.0005 means tight spread (good)
    decision, probability = get_xgboost_signal(
        price_history=fake_history,
        breadth=0.55,
        spread_proxy=0.0005,
        threshold=0.65
    )
    
    print(f"\nFinal Result:")
    print(f"Decision:    {decision}")
    print(f"Probability: {probability:.3f}")
    print(f"Trade?       {'YES!' if decision == 'BUY' else 'No, skip'}")