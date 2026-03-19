"""
Watchdog — runs separately from the bot.
Checks if main.py is alive every 5 minutes.
If the bot is dead, sends a Telegram alert and restarts it.

Run: python3 watchdog.py
Best to run in a separate tmux session: tmux new -s watchdog
"""

import subprocess
import time
import requests
import os

TELEGRAM_TOKEN = "8742026308:AAHDWHuAX8W4YJKAg13Wq48eCAKYXVRfcnk"
TELEGRAM_CHAT_ID = "-5271669161"
CHECK_INTERVAL = 300  # Check every 5 minutes
BOT_DIR = os.path.dirname(os.path.abspath(__file__))


def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
    except Exception:
        pass


def is_bot_running():
    """Check if main.py is running as a process."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "python3 main.py"],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def start_bot():
    """Start the bot in the background."""
    try:
        subprocess.Popen(
            ["python3", "main.py"],
            cwd=BOT_DIR,
            stdout=open(os.path.join(BOT_DIR, "logs", "bot_stdout.log"), "a"),
            stderr=open(os.path.join(BOT_DIR, "logs", "bot_stderr.log"), "a"),
        )
        return True
    except Exception as e:
        send_telegram(f"<b>WATCHDOG ERROR</b>\nFailed to restart bot: {e}")
        return False


if __name__ == "__main__":
    print("Watchdog started. Checking bot every 5 minutes.")
    send_telegram("<b>WATCHDOG STARTED</b>\nMonitoring bot process every 5 minutes.")

    consecutive_failures = 0

    while True:
        try:
            if is_bot_running():
                if consecutive_failures > 0:
                    send_telegram("<b>BOT RECOVERED</b>\nBot is running again.")
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                send_telegram(
                    f"<b>BOT IS DOWN</b>\n"
                    f"main.py not running (check #{consecutive_failures})\n"
                    f"Attempting restart..."
                )
                if start_bot():
                    time.sleep(10)  # Give it a moment to start
                    if is_bot_running():
                        send_telegram("<b>BOT RESTARTED</b>\nSuccessfully restarted main.py")
                    else:
                        send_telegram("<b>RESTART FAILED</b>\nBot did not come back up. Check logs on EC2.")

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("Watchdog stopped.")
            break
        except Exception as e:
            print(f"Watchdog error: {e}")
            time.sleep(CHECK_INTERVAL)
