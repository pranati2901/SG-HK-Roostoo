import pandas as pd
import numpy as np

def create_labels(df, forward_bars=4, profit_threshold=0.001):
    """
    Creates binary labels for XGBoost training
    
    forward_bars = how many candles ahead to check
                   4 bars x 15min = 1 hour ahead
    
    profit_threshold = minimum profit to count as success
                       0.001 = 0.1% (covers fees + minimum profit)
    """
    print("Creating labels...")
    
    data = df.copy()
    
    # Calculate forward return
    # "How much does price change N bars from now?"
    data['future_price'] = data['close'].shift(-forward_bars)
    data['forward_return'] = (data['future_price'] - data['close']) / data['close']
    
    # Create binary label
    # 1 = price goes up enough to be profitable
    # 0 = price doesn't go up enough (don't trade)
    data['label'] = (data['forward_return'] > profit_threshold).astype(int)
    
    # Drop last 4 rows (no future price available)
    data = data.dropna(subset=['future_price'])
    data = data.reset_index(drop=True)
    
    # Show label distribution
    label_counts = data['label'].value_counts()
    total = len(data)
    print(f"Total rows: {total}")
    print(f"Label 1 (BUY): {label_counts[1]} ({100*label_counts[1]/total:.1f}%)")
    print(f"Label 0 (SKIP): {label_counts[0]} ({100*label_counts[0]/total:.1f}%)")
    
    return data

# Load features CSV
print("Loading btc_features.csv...")
df = pd.read_csv('btc_features.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
print(f"Loaded {len(df)} rows")

# Create labels
df_labeled = create_labels(df, forward_bars=4, profit_threshold=0.001)

# Save
df_labeled.to_csv('btc_labeled.csv', index=False)
print("Saved to btc_labeled.csv")
print(df_labeled[['timestamp', 'close', 'forward_return', 'label']].head(10))
