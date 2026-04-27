import os
import requests
import time
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN   = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SYMBOL  = "BTCUSDT"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    })

def get_klines(symbol, interval, limit=20):
    url = "https://api.mexc.com/api/v3/klines"
    r = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit})
    candles = []
    for d in r.json():
        candles.append({
            "time":  int(d[0]),
            "open":  float(d[1]),
            "high":  float(d[2]),
            "low":   float(d[3]),
            "close": float(d[4]),
        })
    return candles

def linreg_slope(values):
    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den != 0 else 0

last_checked = None

def check():
    global last_checked

    candles_5m  = get_klines(SYMBOL, "5m",  limit=20)
    candles_15m = get_klines(SYMBOL, "15m", limit=5)

    last_closed    = candles_5m[-2]
    last_closed_dt = datetime.fromtimestamp(last_closed["time"] / 1000, tz=timezone.utc)

    if last_closed_dt.minute % 15 != 0:
        return

    if last_closed["time"] == last_checked:
        return
    last_checked = last_closed["time"]

    prev_15m_high = candles_15m[-2]["high"]
    prev_15m_low  = candles_15m[-2]["low"]

    entry        = last_closed["close"]
    third_candle = candles_5m[-3]

    reg_closes = [c["close"] for c in candles_5m[-14:-2]]
    if len(reg_closes) < 12:
        return

    slope      = linreg_slope(reg_closes)
    trend_up   = slope > 0
    trend_down = slope < 0

    time_str = last_closed_dt.strftime("%H:%M")

    if entry > prev_15m_high and trend_up:
        sl = third_candle["low"]
        tp = entry + (entry - sl)
        msg = (
            f"🟢 <b>BUY SETUP — {SYMBOL}</b>\n"
            f"⏰ {time_str} UTC\n\n"
            f"📍 Entry : <b>{entry:.2f}</b>\n"
            f"🛑 SL    : {sl:.2f}  (-{entry - sl:.2f})\n"
            f"🎯 TP    : {tp:.2f}  (+{tp - entry:.2f})\n"
            f"📐 Trend : ↑ Uptrend"
        )
        send_telegram(msg)

    elif entry < prev_15m_low and trend_down:
        sl = third_candle["high"]
        tp = entry - (sl - entry)
        msg = (
            f"🔴 <b>SELL SETUP — {SYMBOL}</b>\n"
            f"⏰ {time_str} UTC\n\n"
            f"📍 Entry : <b>{entry:.2f}</b>\n"
            f"🛑 SL    : {sl:.2f}  (+{sl - entry:.2f})\n"
            f"🎯 TP    : {tp:.2f}  (-{entry - tp:.2f})\n"
            f"📐 Trend : ↓ Downtrend"
        )
        send_telegram(msg)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot running")
    def log_message(self, *args):
        pass

def run_server():
    HTTPServer(("0.0.0.0", 10000), Handler).serve_forever()

threading.Thread(target=run_server, daemon=True).start()

print("Bot ishga tushdi...")
send_telegram("✅ Bot ishga tushdi. Setup kuzatilmoqda...")

while True:
    try:
        check()
    except Exception as e:
        print(f"Xato: {e}")
    time.sleep(30)
