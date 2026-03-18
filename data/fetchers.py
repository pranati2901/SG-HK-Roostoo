"""
Data Fetchers: Fear & Greed, Funding Rate, Market Breadth
Owner: Alankritha

Also includes order precision helpers (S5).

STUB FILE — Alankritha implements all fetchers.
"""

import requests


def fetch_fear_greed() -> int:
    """
    Fetch Fear & Greed Index (0-100).
    API: https://api.alternative.me/fng/
    Free, no key needed.

    Returns:
        int: 0 (extreme fear) to 100 (extreme greed)

    TODO (Alankritha):
    - Call the API
    - Parse JSON: response['data'][0]['value']
    - Handle errors gracefully (return 50 as default)
    """
    try:
        resp = requests.get('https://api.alternative.me/fng/?limit=1', timeout=10)
        data = resp.json()
        return int(data['data'][0]['value'])
    except Exception:
        return 50  # Neutral default


def fetch_funding_rate() -> float:
    """
    Fetch BTC perpetual funding rate from Binance.

    Returns:
        float: funding rate (positive = longs pay, negative = shorts pay)

    TODO (Alankritha):
    - Call Binance API for BTCUSDT funding rate
    - Parse and return the rate
    - Handle errors (return 0.0 as default)
    """
    # PLACEHOLDER
    return 0.0


def fetch_market_breadth() -> float:
    """
    Calculate % of top coins trending up (from Binance, NOT Roostoo).

    Returns:
        float: 0.0 to 1.0 (e.g., 0.65 = 65% of coins trending up)

    TODO (Alankritha):
    - Fetch top 20-30 coin prices from Binance
    - Calculate 1-hour % change for each
    - Return fraction that are positive
    - Handle errors (return 0.5 as default)
    """
    # PLACEHOLDER
    return 0.5


def get_order_precision(client) -> dict:
    """
    Fetch PricePrecision and AmountPrecision from Roostoo exchangeInfo.
    Cache on startup.

    Returns:
        {'price_precision': int, 'amount_precision': int, 'min_order': float}

    TODO (Alankritha):
    - Call client.get_exchange_info()
    - Find BTC_USDT pair info
    - Extract PricePrecision, AmountPrecision, MiniOrder
    - Return as dict
    """
    # PLACEHOLDER
    return {'price_precision': 2, 'amount_precision': 6, 'min_order': 0.0001}


def round_price(price: float, precision: int = 2) -> float:
    """Round price to exchange precision."""
    return round(price, precision)


def round_amount(amount: float, precision: int = 6) -> float:
    """Round BTC amount to exchange precision."""
    return round(amount, precision)
