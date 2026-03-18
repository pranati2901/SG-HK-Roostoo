# Quant Trading Bot — SG vs HK Hackathon 2026

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your API keys in config.py
# Get keys from jolly@roostoo.com

# 3. Run the bot
python bot.py
```

## Project Structure

```
quant-hackathon/
├── config.py           # API keys + strategy settings (EDIT THIS FIRST)
├── roostoo_client.py   # API client (handles auth, signing, all API calls)
├── indicators.py       # Technical indicators (MA, RSI, Bollinger, MACD)
├── strategy.py         # Strategy engine (combines signals → BUY/SELL/HOLD)
├── risk_manager.py     # Risk management (position sizing, stop loss, take profit)
├── bot.py              # Main bot loop (runs 24/7)
├── backtest.py         # Backtesting with simulated data
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Strategy: Multi-Signal Momentum + Mean Reversion Hybrid

The bot uses 4 technical indicators that each vote BUY/SELL/NEUTRAL:

1. **Moving Average Crossover** — Trend direction
2. **RSI** — Overbought/oversold detection
3. **Bollinger Bands** — Price extreme detection
4. **MACD** — Momentum confirmation

Trade executes when 2+ signals agree (high confidence).

## Risk Management

- Max 30% of portfolio per trade
- 3% stop loss
- 5% take profit
- Max 5 concurrent open orders
