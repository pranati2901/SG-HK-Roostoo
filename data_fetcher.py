import requests
import pandas as pd
from datetime import datetime, timedelta
import time

def fetch_btc_data(days=90, timeframe='15m'):
    print("Fetching BTC data from Binance...")
    
    # Convert timeframe to milliseconds
    tf_ms = 15 * 60 * 1000  # 15 minutes in milliseconds
    
    # Start time = 90 days ago
    end_time = int(time.time() * 1000)
    start_time = end_time - (days * 24 * 60 * 60 * 1000)
    
    all_candles = []
    current_start = start_time
    
    while current_start < end_time:
        url = "https://api.binance.com/api/v3/klines"
        params = {
            'symbol': 'BTCUSDT',
            'interval': timeframe,
            'startTime': current_start,
            'endTime': end_time,
            'limit': 1000
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            break
            
        candles = response.json()
        
        if not candles:
            break
            
        all_candles += candles
        current_start = candles[-1][0] + tf_ms
        print(f"Downloaded {len(all_candles)} candles so far...")
        
        # Small delay to avoid rate limiting
        time.sleep(0.1)
    
    # Convert to DataFrame
    df = pd.DataFrame(all_candles, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])
    
    # Keep only what we need
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    
    # Convert types
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    
    # Clean up
    df = df.drop_duplicates(subset='timestamp')
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    print(f"Done! Downloaded {len(df)} candles")
    print(f"From: {df['timestamp'].min()}")
    print(f"To:   {df['timestamp'].max()}")
    print(df.head())
    
    return df

# Run it
df = fetch_btc_data(days=90, timeframe='15m')
df.to_csv('btc_data.csv', index=False)
print("Saved to btc_data.csv")