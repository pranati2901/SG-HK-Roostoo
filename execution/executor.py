"""
Layer 7: Execution + Trade Management
Owner: Kireeti

Implements entry execution, trailing exits, time exits, cooldowns, logging,
monitoring, and state persistence for BTC spot trading on Roostoo.
"""

import json
import os
import sys
import time
import threading
from typing import Optional
from datetime import datetime, timedelta, timezone

# Allow running this module directly without installing the package.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import (
    TRADING_PAIR,
    LIMIT_ORDER_TIMEOUT,
    BREAKOUT_AGGRESSIVE_OFFSET,
    PARTIAL_FILL_THRESHOLD,
    ATR_STOP_MULTIPLIER,
    TIME_EXIT_HOURS,
    FLAT_THRESHOLD,
    COOLDOWN_AFTER_STOP,
    MAKER_FEE,
    MAX_POSITION_PCT,
)


BOT_STATE_FILE = "bot_state.json"
TRADES_LOG_FILE = "trades_log.json"
EVENTS_LOG_FILE = "events_log.json"
ALERTS_LOG_FILE = "alerts_log.txt"
DAILY_SUMMARY_FILE = "daily_summary.txt"
HEARTBEAT_FILE = "heartbeat.json"


# --- FUNCTION: _utc_now ---
# What it does: Gets the current time in UTC (world standard time).
# Why we need it: Using UTC avoids time zone confusion across servers.
# Inputs: none.
# Outputs: a timezone-aware datetime object.
def _utc_now():
    # Return the current time in UTC so all logs are consistent.
    return datetime.now(timezone.utc)


# --- FUNCTION: _iso_now ---
# What it does: Returns the current UTC time as a text string.
# Why we need it: Logs and JSON files need time as a readable string.
# Inputs: none.
# Outputs: ISO8601 string like "2026-03-19T12:00:00+00:00".
def _iso_now():
    # Convert the UTC time into ISO format for easy storage.
    return _utc_now().isoformat()


# --- FUNCTION: _write_json_line ---
# What it does: Appends one JSON record to a file.
# Why we need it: We keep a growing list of trade events and logs.
# Inputs: path (file path), payload (a dictionary of data).
# Outputs: none (writes to disk).
def _write_json_line(path: str, payload: dict):
    # Open the file and append one line of JSON text.
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


# --- FUNCTION: _write_text_line ---
# What it does: Appends one plain text line to a file.
# Why we need it: Alerts are human-readable and easier in plain text.
# Inputs: path (file path), line (text to append).
# Outputs: none.
def _write_text_line(path: str, line: str):
    # Append a single line of text with a newline at the end.
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# --- FUNCTION: _round_value ---
# What it does: Rounds a number to a fixed number of decimals.
# Why we need it: The exchange only accepts certain decimal places.
# Inputs: value (number), precision (how many decimals).
# Outputs: rounded number.
def _round_value(value: float, precision: int) -> float:
    # Use Python's round to respect exchange precision rules.
    return round(value, precision)


# --- FUNCTION: _log_event ---
# What it does: Writes a non-trade event to the events log.
# Why we need it: We track things like "signal blocked" or "partial fill".
# Inputs: description (human text), details (extra data).
# Outputs: none.
def _log_event(description: str, details: Optional[dict] = None):
    # Build a log record with a timestamp and message.
    payload = {"timestamp": _iso_now(), "description": description}
    # If extra details exist, merge them in.
    if details:
        payload.update(details)
    # Append to the events log file as JSON.
    _write_json_line(EVENTS_LOG_FILE, payload)


# --- FUNCTION: _alert ---
# What it does: Sends a message to stderr and appends to alerts log.
# Why we need it: Important events should be loud and visible.
# Inputs: message (text to alert).
# Outputs: none.
def _alert(message: str):
    # Print to stderr so it stands out in logs.
    print(message, file=sys.stderr)
    # Also write the alert to a log file for later review.
    _write_text_line(ALERTS_LOG_FILE, message)


# --- FUNCTION: _load_state ---
# What it does: Loads saved bot state from disk.
# Why we need it: After a crash, we must remember open positions and limits.
# Inputs: none.
# Outputs: a state dictionary.
def _load_state() -> dict:
    # If the file does not exist, create a safe default state.
    if not os.path.exists(BOT_STATE_FILE):
        return {
            "position_open": False,
            "position_btc_qty": 0.0,
            "entry_price": 0.0,
            "current_stop": 0.0,
            "position_open_time": None,
            "regime_at_entry": None,
            "current_capital": 1_000_000.0,
            "peak_portfolio_value": 1_000_000.0,
            "cooldown_until": None,
            "halt_until": None,
            "trade_history": [],
            "drawdown_alerts_fired": {"2pct": False, "5pct": False, "8pct": False},
        }
    # Otherwise, load existing state from disk.
    with open(BOT_STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# --- FUNCTION: _save_state ---
# What it does: Saves the bot state to disk.
# Why we need it: If the bot stops, we can resume safely.
# Inputs: state (dictionary to save).
# Outputs: none.
def _save_state(state: dict):
    # Write the full state dictionary to disk as JSON.
    with open(BOT_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# --- FUNCTION: _update_peak ---
# What it does: Updates the highest portfolio value seen.
# Why we need it: Drawdown is measured from the peak.
# Inputs: state (memory), portfolio_value (current money).
# Outputs: none.
def _update_peak(state: dict, portfolio_value: float):
    # Read the stored peak; default to current if missing.
    peak = state.get("peak_portfolio_value", portfolio_value)
    # If current value is higher, update the peak.
    if portfolio_value > peak:
        peak = portfolio_value
    # Save the updated peak into state.
    state["peak_portfolio_value"] = peak


# --- FUNCTION: _cooldown_active ---
# What it does: Checks if we are in a post-stop cooldown.
# Why we need it: Prevents "revenge trading" right after a loss.
# Inputs: state (memory with cooldown_until timestamp).
# Outputs: True if we must wait, False if we can trade.
def _cooldown_active(state: dict) -> bool:
    # Read the saved cooldown time.
    cooldown_until = state.get("cooldown_until")
    # If no cooldown is set, we are not in cooldown.
    if not cooldown_until:
        return False
    # Compare current time with cooldown end time.
    return _utc_now() < datetime.fromisoformat(cooldown_until)


# --- FUNCTION: _set_cooldown ---
# What it does: Sets a cooldown timer for N hours.
# Why we need it: Gives the market time to calm down after a stop-loss.
# Inputs: state (memory), hours (how long to wait).
# Outputs: none.
def _set_cooldown(state: dict, hours: int):
    # Save a future time when cooldown ends.
    state["cooldown_until"] = (_utc_now() + timedelta(hours=hours)).isoformat()


# --- FUNCTION: _entry_price_for_signal ---
# What it does: Calculates the limit price for entry.
# Why we need it: Different signals need different entry behavior.
# Inputs: current_bid, signal_source, price_precision.
# Outputs: limit price rounded to exchange rules.
def _entry_price_for_signal(current_bid: float, signal_source: str, price_precision: int) -> float:
    # If this is a Donchian breakout, we pay a small premium to get filled.
    # BREAKOUT_AGGRESSIVE_OFFSET = 0.0002 means 0.02% above bid.
    if signal_source == "DONCHIAN_BREAKOUT":
        price = current_bid * (1 + BREAKOUT_AGGRESSIVE_OFFSET)
    else:
        # For mean-reversion, use the bid price (no chasing).
        price = current_bid
    # Round price to the exchange precision (e.g., 2 decimals).
    return _round_value(price, price_precision)


# --- FUNCTION: _calc_btc_qty ---
# What it does: Converts USD size into BTC quantity.
# Why we need it: The exchange wants exact BTC amount, not dollars.
# Inputs: final_position_size_usd, current_btc_price, amount_precision.
# Outputs: rounded BTC quantity.
def _calc_btc_qty(final_position_size_usd: float, current_btc_price: float, amount_precision: int) -> float:
    # Calculate raw BTC amount: dollars / price.
    raw_qty = 0.0 if current_btc_price <= 0 else final_position_size_usd / current_btc_price
    # Round to allowed decimal places to avoid API rejection.
    return _round_value(raw_qty, amount_precision)


# --- FUNCTION: _pnl_with_fees ---
# What it does: Computes profit/loss after fees.
# Why we need it: We care about net P&L, not just gross movement.
# Inputs: entry_price, exit_price, qty.
# Outputs: dict with gross P&L, net P&L, percent, and fees.
def _pnl_with_fees(entry_price: float, exit_price: float, qty: float) -> dict:
    # Gross P&L is price change times quantity.
    gross_pnl = (exit_price - entry_price) * qty
    # Maker fee (0.05%) is charged on both entry and exit.
    fee_entry = entry_price * qty * MAKER_FEE
    fee_exit = exit_price * qty * MAKER_FEE
    # Total fees are the sum of both sides.
    total_fees = fee_entry + fee_exit
    # Net P&L is gross minus fees.
    net_pnl = gross_pnl - total_fees
    # P&L percent uses entry price as the base.
    pnl_pct = (exit_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
    return {
        "pnl_usd_gross": gross_pnl,
        "pnl_usd_net": net_pnl,
        "pnl_pct": pnl_pct,
        "fees_paid_usd": total_fees,
    }


# --- FUNCTION: _poll_order ---
# What it does: Repeatedly checks the exchange for order status.
# Why we need it: Limit orders can take time; we must wait for fill.
# Inputs: client, order_id, timeout_seconds, sleep_seconds.
# Outputs: dict with status, filled_qty, avg_price.
#
# Polling means "checking again and again" every few seconds.
def _poll_order(client, order_id: str, timeout_seconds: int, sleep_seconds: int = 10) -> dict:
    # Set the time when we stop waiting.
    deadline = time.time() + timeout_seconds
    # Start with a default status (not filled).
    last = {"status": "NEW", "filled_qty": 0.0, "avg_price": 0.0}
    # Keep checking until we hit the deadline.
    while time.time() < deadline:
        # Ask the exchange for our orders.
        resp = client.query_orders(pair=TRADING_PAIR, pending_only=False)
        # The exchange returns a list; we search for our order id.
        for rows in resp.values() if isinstance(resp, dict) else []:
            for row in rows:
                if str(row.get("OrderID")) == str(order_id):
                    # Capture current status from exchange.
                    last = {
                        "status": (row.get("Status") or "").upper(),
                        "filled_qty": float(row.get("FilledQty", 0) or 0),
                        "avg_price": float(row.get("AvgPrice", 0) or 0),
                    }
                    # If filled or partially filled, stop waiting.
                    if last["status"] in {"FILLED", "PARTIALLY_FILLED"}:
                        return last
        # Wait a bit before checking again.
        time.sleep(sleep_seconds)
    # If time runs out, return the last known status.
    return last


class TradeExecutor:
    # --- FUNCTION: __init__ ---
    # What it does: Initializes the executor with client and precision rules.
    # Why we need it: We need exchange access and saved state before trading.
    # Inputs: client (API object), price_precision, amount_precision.
    # Outputs: None (sets up internal state).
    def __init__(self, client, price_precision: int, amount_precision: int):
        # Save the exchange client so we can place orders.
        self.client = client
        # Save precision rules so we can round prices and quantities.
        self.price_precision = price_precision
        self.amount_precision = amount_precision
        # Load saved state so we remember open positions after a crash.
        self.state = _load_state()
        # Create a lock so threads do not overwrite each other.
        self.lock = threading.Lock()
        # Placeholder for the stop-monitor thread.
        self.stop_thread = None

    # --- FUNCTION: _log_trade ---
    # What it does: Writes a full trade record to the trades log.
    # Why we need it: We must analyze trades later and generate daily summaries.
    # Inputs: entry (trade dictionary with all fields).
    # Outputs: none.
    def _log_trade(self, entry: dict):
        # Append the trade record to the JSON log file.
        _write_json_line(TRADES_LOG_FILE, entry)

    # --- FUNCTION: _log_event ---
    # What it does: Writes non-trade events to the events log.
    # Why we need it: We need visibility into rejections, cooldowns, errors.
    # Inputs: description (text), details (extra data).
    # Outputs: none.
    def _log_event(self, description: str, details: Optional[dict] = None):
        # Forward the event to the shared logger.
        _log_event(description, details)

    # --- FUNCTION: _heartbeat ---
    # What it does: Writes a heartbeat file every time we call it.
    # Why we need it: External watchers check this to know the bot is alive.
    # Inputs: none.
    # Outputs: none (writes heartbeat.json).
    def _heartbeat(self):
        # Get current portfolio and peak for drawdown display.
        portfolio = self.state.get("current_capital", 0.0)
        peak = self.state.get("peak_portfolio_value", portfolio)
        dd = (peak - portfolio) / peak * 100 if peak else 0.0
        # Build heartbeat JSON payload.
        payload = {"last_heartbeat": _iso_now(), "status": "alive", "portfolio_value": float(portfolio)}
        # Write heartbeat file so watchdogs can read it.
        with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        # Also print a readable line for logs.
        print(f"HEARTBEAT: {_iso_now()} | Portfolio: ${portfolio:,.0f} | Drawdown: {dd:.2f}%")

    # --- FUNCTION: _alert_drawdown_crossings ---
    # What it does: Sends alerts when drawdown crosses key levels.
    # Why we need it: Early warnings prevent silent blowups.
    # Inputs: none (uses state values).
    # Outputs: none.
    def _alert_drawdown_crossings(self):
        # Calculate drawdown from peak.
        portfolio = self.state.get("current_capital", 0.0)
        peak = self.state.get("peak_portfolio_value", portfolio)
        dd = (peak - portfolio) / peak if peak else 0.0
        # Track which alerts have already fired so we do not spam.
        alerts = self.state.get("drawdown_alerts_fired", {"2pct": False, "5pct": False, "8pct": False})
        # If drawdown crosses 2%, alert once.
        if dd >= 0.02 and not alerts.get("2pct"):
            _alert("ALERT: Drawdown crossed 2.0% — entering cautious mode")
            alerts["2pct"] = True
        # If drawdown crosses 5%, alert once.
        if dd >= 0.05 and not alerts.get("5pct"):
            _alert("ALERT: Drawdown crossed 5.0% — position cap at 15%")
            alerts["5pct"] = True
        # If drawdown crosses 8%, alert once.
        if dd >= 0.08 and not alerts.get("8pct"):
            _alert("ALERT ⚠️: Drawdown crossed 8.0% — TRADING HALTED 4 hours")
            alerts["8pct"] = True
        # Save the updated alert flags.
        self.state["drawdown_alerts_fired"] = alerts

    # --- FUNCTION: _daily_summary ---
    # What it does: Writes a daily summary report.
    # Why we need it: Daily metrics show if the strategy is healthy.
    # Inputs: trades (list of trades for the day).
    # Outputs: none (writes to daily_summary.txt).
    def _daily_summary(self, trades: list):
        # If there are no trades, skip writing a summary.
        if not trades:
            return
        # Separate wins and losses for win rate.
        wins = [t for t in trades if t.get("pnl_usd_net", 0) > 0]
        losses = [t for t in trades if t.get("pnl_usd_net", 0) <= 0]
        n = len(trades)
        # Sum up total P&L for the day.
        pnl_today = sum(t.get("pnl_usd_net", 0) for t in trades)
        # Find best and worst trade for risk inspection.
        best = max((t.get("pnl_usd_net", 0) for t in trades), default=0)
        worst = min((t.get("pnl_usd_net", 0) for t in trades), default=0)
        # Average hold time helps see if trades are too short/long.
        avg_hold = sum(t.get("hold_hours", 0) for t in trades) / max(n, 1)
        # Current portfolio and drawdown.
        portfolio = self.state.get("current_capital", 0.0)
        peak = self.state.get("peak_portfolio_value", portfolio)
        dd = (peak - portfolio) / peak * 100 if peak else 0.0
        # Win percentage.
        win_pct = (len(wins) / n * 100) if n else 0.0
        # Build the summary text.
        summary = (
            f"=== DAILY SUMMARY {_utc_now().date()} ===\n"
            f"Trades today: {n}\n"
            f"Win rate: {len(wins)}/{n} = {win_pct:.1f}%\n"
            f"Total P&L today: ${pnl_today:+,.2f}\n"
            f"Current portfolio: ${portfolio:,.0f}\n"
            f"Current drawdown from peak: {dd:.2f}%\n"
            f"Sharpe estimate (today): 0.00\n"
            f"Largest loss: ${worst:+,.2f}\n"
            f"Largest win: ${best:+,.2f}\n"
            f"Avg hold time: {avg_hold:.1f}h"
        )
        # Write the summary to disk.
        _write_text_line(DAILY_SUMMARY_FILE, summary)

    # --- FUNCTION: _enter_position ---
    # What it does: Executes the full entry process for a BUY order.
    # Why we need it: This is where we actually place the order on the exchange.
    # Inputs:
    #   final_position_size_usd (approved size from Layer 6),
    #   current_bid (current bid price),
    #   current_btc_price (last price),
    #   signal_source (DONCHIAN_BREAKOUT or MEAN_REVERSION).
    # Outputs: dict with order info if filled, or None if not filled.
    def _enter_position(self, final_position_size_usd: float, current_bid: float, current_btc_price: float,
                        signal_source: str):
        # Safety S2: If a position is already open, ignore new BUY signals.
        if self.state.get("position_open"):
            self._log_event("BUY signal ignored: position already open")
            return None

        # Step 1: Convert USD size into BTC quantity and round to precision.
        qty = _calc_btc_qty(final_position_size_usd, current_btc_price, self.amount_precision)
        # If rounding makes quantity zero, the order is too small to place.
        if qty == 0:
            self._log_event("Position too small after rounding, skipping")
            return None

        # Step 2: Compute limit price based on signal type.
        limit_price = _entry_price_for_signal(current_bid, signal_source, self.price_precision)

        # Step 3: Place the LIMIT BUY order on the exchange.
        # We are asking the exchange to buy "qty" BTC at "limit_price" or better.
        order = self.client.place_order(TRADING_PAIR, "BUY", "LIMIT", qty, limit_price)
        # The exchange returns an order id (like a receipt number).
        order_id = order.get("OrderID")

        # Step 4: Wait up to 2 minutes for fill, checking every 10 seconds.
        status = _poll_order(self.client, order_id, LIMIT_ORDER_TIMEOUT, sleep_seconds=10)
        if status["status"] == "FILLED":
            # If filled, return the fill details using actual average price.
            return {"order_id": order_id, "qty": qty, "fill_price": status["avg_price"] or limit_price}

        # Step 4b: If partial fill, apply partial fill rules.
        if status["status"] == "PARTIALLY_FILLED":
            # Compute filled percentage (e.g., 0.6 means 60%).
            filled_pct = status["filled_qty"] / qty if qty > 0 else 0
            if filled_pct > PARTIAL_FILL_THRESHOLD:
                # If >50% filled, accept as valid position.
                self._log_event("Partial fill ACCEPTED", {"filled_pct": filled_pct})
                return {"order_id": order_id, "qty": status["filled_qty"], "fill_price": status["avg_price"] or limit_price}
            # If <=50% filled, cancel and sell back immediately.
            self.client.cancel_order(order_id)
            # Market SELL means "sell immediately at best available price".
            self.client.place_order(TRADING_PAIR, "SELL", "MARKET", status["filled_qty"], 0)
            # Set a 60-second cooldown to avoid immediate re-entry.
            self.state["cooldown_until"] = (_utc_now() + timedelta(seconds=60)).isoformat()
            _save_state(self.state)
            self._log_event("Partial fill REJECTED", {"filled_pct": filled_pct})
            return None

        # Step 5: Retry once with updated price.
        self.client.cancel_order(order_id)
        ticker = self.client.get_ticker(TRADING_PAIR)
        bid = float(ticker.get("MaxBid", current_bid)) if isinstance(ticker, dict) else current_bid
        limit_price = _entry_price_for_signal(bid, signal_source, self.price_precision)
        order = self.client.place_order(TRADING_PAIR, "BUY", "LIMIT", qty, limit_price)
        order_id = order.get("OrderID")
        status = _poll_order(self.client, order_id, LIMIT_ORDER_TIMEOUT, sleep_seconds=10)
        if status["status"] == "FILLED":
            return {"order_id": order_id, "qty": qty, "fill_price": status["avg_price"] or limit_price}

        # Step 5b: If still not filled, cancel and abandon the signal.
        self.client.cancel_order(order_id)
        self._log_event("Signal abandoned after 2 attempts — price moved away.")
        return None

    # --- FUNCTION: _exit_position ---
    # What it does: Sells BTC to close an open position.
    # Why we need it: This is how we realize profits or cut losses.
    # Inputs: exit_reason (why we are exiting), current_bid (exit price reference).
    # Outputs: trade entry dict if exit succeeds, or None.
    def _exit_position(self, exit_reason: str, current_bid: float):
        # Safety S1: If no position is open, do nothing.
        if not self.state.get("position_open"):
            self._log_event("SELL ignored: no position open")
            return None

        # Read current position quantity.
        qty = self.state.get("position_btc_qty", 0.0)
        # If quantity is invalid, do nothing.
        if qty <= 0:
            self._log_event("SELL ignored: invalid position qty")
            return None

        # First try a LIMIT SELL at the bid to save fees.
        limit_price = _round_value(current_bid, self.price_precision)
        order = self.client.place_order(TRADING_PAIR, "SELL", "LIMIT", qty, limit_price)
        order_id = order.get("OrderID")
        # Wait up to 60 seconds to fill.
        status = _poll_order(self.client, order_id, 60, sleep_seconds=10)
        if status["status"] != "FILLED":
            # If not filled, use a MARKET SELL to get out quickly.
            self.client.place_order(TRADING_PAIR, "SELL", "MARKET", qty, 0)
            status = _poll_order(self.client, order_id, 10, sleep_seconds=2)

        # Use actual average fill price if available; otherwise use limit.
        exit_price = status["avg_price"] or limit_price
        entry_price = self.state.get("entry_price", 0.0)
        # Calculate P&L after fees.
        pnl = _pnl_with_fees(entry_price, exit_price, qty)

        # Update portfolio value with net P&L.
        portfolio = self.state.get("current_capital", 0.0) + pnl["pnl_usd_net"]
        self.state["current_capital"] = portfolio
        # Update peak value if we made a new high.
        _update_peak(self.state, portfolio)
        # Clear position fields after exit.
        self.state["position_open"] = False
        self.state["position_btc_qty"] = 0.0
        self.state["entry_price"] = 0.0
        self.state["current_stop"] = 0.0
        self.state["position_open_time"] = None

        # If exit reason includes STOP, set cooldown for 1 hour.
        if "STOP" in exit_reason:
            _set_cooldown(self.state, COOLDOWN_AFTER_STOP / 3600)

        # Build the full trade log record with all required fields.
        trade_entry = {
            "timestamp": _iso_now(),
            "regime": self.state.get("regime_at_entry"),
            "signal_source": self.state.get("signal_source"),
            "reversal_blocker_result": self.state.get("reversal_blocker_result"),
            "xgboost_probability": self.state.get("xgboost_probability"),
            "timeframe_scores": self.state.get("timeframe_scores"),
            "timeframe_total_score": self.state.get("timeframe_total_score"),
            "position_size_usd": self.state.get("position_size_usd"),
            "position_size_btc": qty,
            "entry_price": entry_price,
            "stop_loss_level": self.state.get("current_stop"),
            "take_profit_level": self.state.get("take_profit_level"),
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "pnl_usd_gross": pnl["pnl_usd_gross"],
            "pnl_usd_net": pnl["pnl_usd_net"],
            "pnl_pct": pnl["pnl_pct"],
            "fees_paid_usd": pnl["fees_paid_usd"],
            "portfolio_value_after": portfolio,
            "drawdown_at_trade_pct": (
                (self.state.get("peak_portfolio_value", portfolio) - portfolio)
                / self.state.get("peak_portfolio_value", portfolio)
                * 100
                if self.state.get("peak_portfolio_value", portfolio) > 0
                else 0.0
            ),
            "cooldown_triggered": "STOP" in exit_reason,
            "partial_fill": False,
            "partial_fill_pct": None,
        }
        # Write the trade to the log.
        self._log_trade(trade_entry)
        # Save state after exit.
        _save_state(self.state)
        return trade_entry

    # --- FUNCTION: _evaluate_trailing ---
    # What it does: Updates trailing stop or checks sideways exits.
    # Why we need it: Protect profits and cut losses quickly.
    # Inputs: entry_price, current_price, atr_14, regime, current_stop.
    # Outputs: (exit_reason or None, new_stop, take_profit).
    def _evaluate_trailing(self, entry_price: float, current_price: float, atr_14: float, regime: str, current_stop: float):
        # If sideways, use fixed take profit and fixed stop loss.
        if regime == "SIDEWAYS":
            # take_profit = entry + 1x ATR (ATR is typical movement).
            take_profit = entry_price + atr_14
            # stop = entry - 1.5x ATR to allow some wiggle room.
            stop = entry_price - ATR_STOP_MULTIPLIER * atr_14
            # If price hits take profit, exit with profit.
            if current_price >= take_profit:
                return "FIXED_TAKE_PROFIT", stop, take_profit
            # If price hits stop, exit with loss.
            if current_price <= stop:
                return "STOP_LOSS_FIXED", stop, take_profit
            # Otherwise no exit yet.
            return None, stop, take_profit

        # TRENDING mode: use trailing stop that only moves up.
        candidate = current_price - ATR_STOP_MULTIPLIER * atr_14
        # The stop can only move higher (never lower).
        new_stop = max(current_stop, candidate)
        # If price crosses below the stop, we exit.
        if current_price <= new_stop:
            return "TRAILING_STOP", new_stop, None
        # Otherwise keep going.
        return None, new_stop, None

    # --- FUNCTION: _should_time_exit ---
    # What it does: Checks if we should exit a flat trade after 8 hours.
    # Why we need it: Dead capital blocks new opportunities.
    # Inputs: entry_price, current_price.
    # Outputs: True if time exit should happen, else False.
    def _should_time_exit(self, entry_price: float, current_price: float) -> bool:
        # Read when the position was opened.
        open_time = self.state.get("position_open_time")
        # If no open time, we cannot time-exit.
        if not open_time:
            return False
        # Calculate how many hours the position has been open.
        hours = (_utc_now() - datetime.fromisoformat(open_time)).total_seconds() / 3600
        # Calculate current P&L percent to see if it is flat.
        pnl_pct = (current_price - entry_price) / entry_price * 100 if entry_price > 0 else 0.0
        # If >= 8 hours and P&L < 0.2%, exit.
        return hours >= TIME_EXIT_HOURS and pnl_pct < FLAT_THRESHOLD * 100

    # --- FUNCTION: start_stop_monitor ---
    # What it does: Starts a background thread to monitor stops.
    # Why we need it: Price can move fast; we check every 10 seconds.
    # Inputs: atr_14, regime.
    # Outputs: none (starts a daemon thread).
    def start_stop_monitor(self, atr_14: float, regime: str):
        def _loop():
            while True:
                # Lock state so main thread and stop thread do not collide.
                with self.lock:
                    # If no position is open, stop the monitor thread.
                    if not self.state.get("position_open"):
                        return
                    # Fetch the latest ticker (price information) from exchange.
                    ticker = self.client.get_ticker(TRADING_PAIR)
                    # Read the current price from the ticker.
                    current_price = float(ticker.get("LastPrice", 0)) if isinstance(ticker, dict) else 0.0
                    # Read entry price and current stop from state.
                    entry = self.state.get("entry_price", 0.0)
                    current_stop = self.state.get("current_stop", 0.0)
                    # Update trailing stop or check sideways exits.
                    reason, new_stop, tp = self._evaluate_trailing(entry, current_price, atr_14, regime, current_stop)
                    # Save updated stop and take-profit levels.
                    self.state["current_stop"] = new_stop
                    self.state["take_profit_level"] = tp
                    # If an exit reason exists, execute exit.
                    if reason:
                        bid = float(ticker.get("MaxBid", current_price)) if isinstance(ticker, dict) else current_price
                        self._exit_position(reason, bid)
                        return
                    # If time-exit condition is met, exit.
                    if self._should_time_exit(entry, current_price):
                        bid = float(ticker.get("MaxBid", current_price)) if isinstance(ticker, dict) else current_price
                        self._exit_position("TIME_EXIT_FLAT", bid)
                        return
                # Wait 10 seconds before checking again.
                time.sleep(10)

        # Start the loop in a daemon thread so it ends with the main process.
        self.stop_thread = threading.Thread(target=_loop, daemon=True)
        self.stop_thread.start()

    # --- FUNCTION: execute_trade ---
    # What it does: Full entry execution for a BUY signal.
    # Why we need it: This is the final step that actually trades.
    # Inputs:
    #   final_position_size_usd, current_btc_price, current_bid, current_ask,
    #   atr_14, regime, signal_source, entry_context (for logging).
    # Outputs: None (it manages state internally).
    def execute_trade(self, final_position_size_usd: float, current_btc_price: float, current_bid: float,
                      current_ask: float, atr_14: float, regime: str,
                      signal_source: str, entry_context: dict):
        # Lock so we do not race with the stop monitor.
        with self.lock:
            # If we are in cooldown, skip this signal.
            if _cooldown_active(self.state):
                self._log_event("In post-stop cooldown. Skipping signal.")
                return

            # Attempt to enter a position using the entry logic.
            entry = self._enter_position(final_position_size_usd, current_bid, current_btc_price, signal_source)
            # If entry failed, save state and stop.
            if not entry:
                _save_state(self.state)
                return

            # Save entry details to state.
            self.state["position_open"] = True
            self.state["position_btc_qty"] = entry["qty"]
            self.state["entry_price"] = entry["fill_price"]
            self.state["position_open_time"] = _iso_now()
            self.state["regime_at_entry"] = regime
            self.state["signal_source"] = signal_source
            self.state["position_size_usd"] = final_position_size_usd
            # Initial stop is entry price minus 1.5x ATR.
            self.state["current_stop"] = entry["fill_price"] - ATR_STOP_MULTIPLIER * atr_14
            self.state["take_profit_level"] = None
            # Copy context for logging later.
            self.state["reversal_blocker_result"] = entry_context.get("reversal_blocker_result")
            self.state["xgboost_probability"] = entry_context.get("xgboost_probability")
            self.state["timeframe_scores"] = entry_context.get("timeframe_scores")
            self.state["timeframe_total_score"] = entry_context.get("timeframe_total_score")

            # Persist state immediately after entry.
            _save_state(self.state)
            # Send an alert that a trade was executed.
            _alert(
                f"TRADE EXECUTED: BUY {entry['qty']:.5f} BTC @ ${entry['fill_price']:,.2f} "
                f"| Size: ${final_position_size_usd:,.0f} | Stop: ${self.state['current_stop']:,.2f}"
            )
            # Start the background stop monitor.
            self.start_stop_monitor(atr_14, regime)
            # Write heartbeat and drawdown alerts.
            self._heartbeat()
            self._alert_drawdown_crossings()


__all__ = [
    "TradeExecutor",
    "_calc_btc_qty",
    "_entry_price_for_signal",
    "_pnl_with_fees",
    "_load_state",
    "_save_state",
]
