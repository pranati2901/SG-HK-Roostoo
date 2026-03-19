# ARM v2 — Adaptive Regime Momentum Trading Bot

**Team177-QuantX (NTU)** | SG vs HK Quant Trading Hackathon 2026

## Strategy Overview

ARM v2 is an autonomous BTC/USD trading bot built for the Roostoo mock exchange. The core insight: **not losing money matters more than making money** (scoring = 0.4 Sortino + 0.3 Sharpe + 0.3 Calmar).

The bot uses a **7-layer decision pipeline** that runs every 60 seconds. Each layer must pass before a trade executes — this creates a high-conviction, low-frequency system that stays in cash during unfavorable conditions.

## The 7-Layer Pipeline

```
Every 60s: Fetch price → L1 → L2 → L3 → L4 → L5 → L6 → L7
```

| Layer | Name | Function |
|-------|------|----------|
| **L1** | Regime Detection | ATR + ADX + BB width + market breadth + Fear & Greed + funding rate → TRENDING / SIDEWAYS / VOLATILE |
| **L2** | Signal Generation | Trending: Donchian breakout, EMA alignment, MACD. Sideways: RSI, Bollinger Band touch, z-score. Volatile: HOLD |
| **L3** | Reversal Blocker | Blocks trades during price spikes (>2% in 3 candles), spread widening (>1.5x avg), or abnormal volume (>3x avg). 2-cycle cooldown |
| **L4** | Multi-Timeframe Filter | Scores 1H/4H/Daily as +1/0/-1. Requires alignment across timeframes. Never trades against 4H trend |
| **L5** | XGBoost Confirmation | Binary classifier trained on 10 engineered features. Minimum 65% probability to trade |
| **L6** | Position Sizing | Adaptive Quarter-Kelly with regime multipliers, drawdown throttle, and emergency kill switch |
| **L7** | Execution Engine | Limit orders at bid, 2-min cancel-replace, trailing stop-loss, time-based exits, partial fill handling |

## Key Design Decisions

- **Directional only** — no shorting, no leverage, no market-making, no arbitrage
- **Limit orders only** — 0.05% maker fee vs 0.1% taker fee (saves 50% on fees)
- **One position at a time** — simplifies risk management and avoids overexposure
- **Volatile regime = HOLD** — the bot correctly stays in cash when markets are chaotic
- **Multi-source data** — combines Roostoo ticker data with Binance funding rates, Fear & Greed index, and cross-market breadth

## Backtest Results (106 days, Dec 2025 - Mar 2026)

| Metric | ARM v2 | Buy & Hold |
|--------|--------|------------|
| Return | +0.06% | -15.0% |
| Final Equity | $50,030 | $42,477 |
| Max Drawdown | 0.15% | 28.3% |
| Trades | 7 | — |
| Win Rate | 43% | — |

**Outperformance: +15.1%** — the bot preserved capital during the bear market by correctly identifying VOLATILE regime and staying in cash.

## Risk Management

- **Drawdown throttle**: 5 escalating levels (2% → 5% → 8% → 10% → 15% kill switch)
- **Position sizing**: Quarter-Kelly clamped between 2-15% of equity
- **Regime multipliers**: TRENDING = 100%, SIDEWAYS = 50%, VOLATILE = 10%
- **Max position**: 35% hard cap
- **Max loss per trade**: 1.5%
- **Post stop-loss cooldown**: 1 hour
- **Time exit**: Flat positions closed after 8 hours

## Project Structure

```
quant-hackathon/
├── main.py                  # Main bot loop — wires all 7 layers
├── config.py                # All tunable parameters
├── config_secrets.py        # API keys (git-ignored)
├── roostoo_client.py        # Roostoo API client (auth, signing, orders)
├── dashboard.py             # Web dashboard at localhost:8080
├── live_predictor.py        # XGBoost live prediction function
├── feature_engineer.py      # Feature engineering for ML model
├── xgboost_trainer.py       # Model training pipeline
├── retrain.py               # Daily model retraining
├── data/
│   ├── candle_builder.py    # Tick aggregation + cold start bootstrap
│   ├── fetchers.py          # Fear & Greed, funding rate, breadth, precision
│   └── state.py             # State persistence (JSON save/load)
├── strategy/
│   ├── regime.py            # L1: Regime Detection
│   ├── signals.py           # L2: Signal Generation
│   ├── reversal_blocker.py  # L3: Reversal Blocker
│   ├── timeframe.py         # L4: Multi-Timeframe Filter
│   └── ml_model.py          # L5: XGBoost integration
├── risk/
│   └── position_sizer.py    # L6: Position Sizing + Risk Management
├── execution/
│   ├── executor.py          # L7: Order Execution
│   └── alerts.py            # Telegram alerts
└── backtest/
    └── backtester.py        # Backtester with equity curve plotting
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Add API keys
# Create config_secrets.py with your Roostoo API keys (git-ignored)

# Run the bot
python main.py

# Run the dashboard (separate terminal)
python dashboard.py
# Open http://localhost:8080
```

## Deployment (AWS)

The bot runs on AWS (ap-southeast-2) on a t3.medium instance inside tmux for persistence across session disconnects.

```bash
# On AWS instance
tmux new -s bot
python main.py
# Ctrl+B, D to detach

# To check on it
tmux attach -t bot
```

## Team

| Member | Role |
|--------|------|
| Narhen | Infrastructure, pipeline architecture, L1/L2/L4, integration |
| Alankritha | L3 Reversal Blocker, data feeds |
| Pranati | L5 XGBoost model, feature engineering, training pipeline |
| Kireeti | L6 Position Sizing, L7 Execution Engine |

## Tech Stack

- **Language**: Python 3
- **ML**: XGBoost, scikit-learn
- **Data**: pandas, numpy, ta (technical analysis)
- **API**: requests, HMAC-SHA256 auth
- **Alerts**: Telegram Bot API
- **Deployment**: AWS EC2 (t3.medium), tmux
- **Dashboard**: Built-in HTTP server (no framework needed)
