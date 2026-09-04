import csv
import os
import time
from datetime import datetime
import urllib.request
import json
import yfinance as yf

# CONFIGURATION SETTINGS
CSV_FILE = "stock_tracker_log.csv"
DISCORD_WEBHOOK_URL = ""  # Optional: Paste your Discord Webhook URL here
TICKERS_TO_CHECK = ["SNDL", "RIG", "SOFI", "PLTR", "LCID"]
MAX_PRICE = 10.00
PRICE_DROP_ALERT_THRESHOLD = -2.5  # Alert if daily drop exceeds -2.5%


def send_discord_alert(message: str):
    """Sends a notification payload to a Discord channel if a URL is supplied."""
    if not DISCORD_WEBHOOK_URL:
        return
    payload = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            pass
    except Exception as e:
        print(f"⚠️ Failed to send Discord alert: {e}")


def initialize_csv():
    """Ensures the local CSV file exists with standard headers."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Ticker", "Price", "OneDayChangePct", "Status"])


def run_tracker():
    """Main execution block: Fetches prices, logs to CSV, and checks alert thresholds."""
    initialize_csv()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n--- Running Tracker Session [{timestamp}] ---")

    for ticker_symbol in TICKERS_TO_CHECK:
        try:
            stock = yf.Ticker(ticker_symbol)
            history = stock.history(period="2d")

            if not history.empty and len(history) >= 2:
                prev_close = history['Close'].iloc[-2]
                curr_price = history['Close'].iloc[-1]
                pct_change = ((curr_price - prev_close) / prev_close) * 100

                if curr_price <= MAX_PRICE:
                    status = "TRACKED"
                    print(f"✅ {ticker_symbol:<5} | Price: ${curr_price:>6.2f} | 1-Day Change: {pct_change:>+6.2f}%")

                    # Check trigger condition for Discord Alert
                    if pct_change <= PRICE_DROP_ALERT_THRESHOLD:
                        alert_msg = f"🚨 **Stock Alert**: {ticker_symbol} dropped {pct_change:.2f}% to ${curr_price:.2f}!"
                        print(f"   ↳ {alert_msg}")
                        send_discord_alert(alert_msg)
                else:
                    status = "SKIPPED_HIGH_PRICE"
                    print(f"⏩ {ticker_symbol:<5} | Skipped (Price ${curr_price:.2f} exceeds limit)")

                # 1. Log entry to local CSV file
                with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, ticker_symbol, round(curr_price, 2), round(pct_change, 2), status])

            else:
                print(f"⚠️ {ticker_symbol:<5} | Data missing or insufficient history.")

        except Exception as err:
            print(f"❌ Error processing {ticker_symbol}: {err}")


def run_scheduler(interval_minutes=60):
    """3. Loop runner: Executes the tracker logic on a recurring interval."""
    print(f"Starting automated schedule. Running every {interval_minutes} minutes. Press Ctrl+C to stop.")
    try:
        while True:
            run_tracker()
            print(f"\nSleeping for {interval_minutes} minutes...")
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        print("\nScheduler manually stopped.")


if __name__ == "__main__":
    # Executes once immediately, then begins loop interval
    run_scheduler(interval_minutes=60)