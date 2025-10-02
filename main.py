# main.py - TradeBot (no pandas) - Flask app
import os, time, csv, math, threading
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file
import requests

# CONFIG
SYMBOLS = os.getenv("SYMBOLS", "ETHUSDT,BTCUSDT,BNBUSDT,SOLUSDT,ADAUSDT").split(",")
INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "10.0"))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "60"))
EMA_FAST = int(os.getenv("EMA_FAST", "8"))
EMA_SLOW = int(os.getenv("EMA_SLOW", "21"))
RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
VOLUME_MULTIPLIER = float(os.getenv("VOLUME_MULTIPLIER", "1.0"))
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "0.01"))
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.02"))
KL_LIMIT = int(os.getenv("KL_LIMIT", "1000"))
BINANCE_KLINES = os.getenv("BINANCE_KLINES", "https://api.binance.com/api/v3/klines")

DEBUG_LOG = "bot_debug.log"
TRADE_LOG = "trades.csv"

app = Flask(__name__, template_folder="templates", static_folder="static")

# Global state
balance_lock = threading.Lock()
balance = INITIAL_BALANCE
current_trade = None
trade_history = []
stats = {"trades":0, "wins":0, "losses":0, "profit_usd":0.0}

def debug(msg):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def fetch_klines(symbol, interval="1m", limit=KL_LIMIT):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    headers = {"User-Agent":"TradeBot-NoPandas/1.0"}
    r = requests.get(BINANCE_KLINES, params=params, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()
    out = []
    for k in data:
        out.append({
            "time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5])
        })
    return out

# Indicators
def ema_list(values, span):
    if not values:
        return []
    alpha = 2.0 / (span + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append((v - out[-1]) * alpha + out[-1])
    return out

def sma_list(values, period):
    out = []
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= period:
            s -= values[i-period]
            out.append(s/period)
        elif i == period-1:
            out.append(s/period)
    return out

def rsi_list(values, period=14):
    if len(values) < period+1:
        return [50.0] * len(values)
    deltas = [values[i] - values[i-1] for i in range(1, len(values))]
    ups = [d if d>0 else 0 for d in deltas]
    downs = [-d if d<0 else 0 for d in deltas]
    up_avg = sum(ups[:period]) / period
    down_avg = sum(downs[:period]) / period if sum(downs[:period])!=0 else 1e-9
    out = [50.0] * (period+1)
    for u, d in zip(ups[period:], downs[period:]):
        up_avg = (up_avg*(period-1) + u) / period
        down_avg = (down_avg*(period-1) + d) / period
        rs = up_avg / (down_avg + 1e-12)
        out.append(100 - (100/(1+rs)))
    return out

def atr_list(highs, lows, closes, period=14):
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
        trs.append(tr)
    if not trs:
        return [0.0]*len(closes)
    if len(trs) < period:
        avg = sum(trs)/len(trs)
        return [avg]*len(closes)
    sma_tr = sma_list(trs, period)
    return [sma_tr[0]]*period + sma_tr

def run_backtest(candles, initial_balance=INITIAL_BALANCE, risk_per_trade=RISK_PER_TRADE, stop_loss_pct=STOP_LOSS_PCT):
    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    vols = [c["volume"] for c in candles]
    times = [c["time"] for c in candles]

    ema_fast = ema_list(closes, EMA_FAST)
    ema_slow = ema_list(closes, EMA_SLOW)
    rsi_vals = rsi_list(closes, RSI_PERIOD)
    atr_vals = atr_list(highs, lows, closes, period=14)
    avg_vol20 = []
    for i in range(len(vols)):
        window = vols[max(0, i-20):i]
        avg_vol20.append(sum(window)/len(window) if window else vols[i])

    balance_local = float(initial_balance)
    position = None
    trades = []
    wins = 0
    losses = 0

    for i in range(len(closes)):
        if i < max(EMA_SLOW, RSI_PERIOD) + 2:
            continue
        price = closes[i]
        prev_i = i-1
        cross_up = (ema_fast[prev_i] <= ema_slow[prev_i]) and (ema_fast[i] > ema_slow[i])
        cross_down = (ema_fast[prev_i] >= ema_slow[prev_i]) and (ema_fast[i] < ema_slow[i])
        vol_ok = vols[i] > (avg_vol20[i] * VOLUME_MULTIPLIER)
        rsi_ok = (rsi_vals[prev_i] > 25 and rsi_vals[prev_i] < 75)

        if position is None:
            if cross_up and vol_ok and rsi_ok:
                risk_amount = balance_local * risk_per_trade
                if stop_loss_pct <= 0:
                    qty = balance_local / price
                else:
                    qty = risk_amount / (price * stop_loss_pct)
                qty = max(qty, 1e-8)
                stop_price = price * (1 - stop_loss_pct)
                position = {"entry": price, "qty": qty, "stop": stop_price, "entry_time": times[i]}
                debug(f"ENTER idx={i} price={price:.6f} qty={qty:.8f} bal={balance_local:.8f}")
        else:
            if lows[i] <= position["stop"]:
                exit_price = position["stop"]
                proceeds = position["qty"] * exit_price
                profit = proceeds - (position["qty"] * position["entry"])
                balance_local = proceeds
                trades.append({"time": times[i], "entry": position["entry"], "exit": exit_price, "profit": profit, "balance_after": balance_local, "reason":"SL"})
                if profit>=0: wins+=1
                else: losses+=1
                debug(f"EXIT SL idx={i} exit={exit_price:.6f} profit={profit:.8f} newbal={balance_local:.8f}")
                position = None
                continue
            if cross_down:
                exit_price = price
                proceeds = position["qty"] * exit_price
                profit = proceeds - (position["qty"] * position["entry"])
                balance_local = proceeds
                trades.append({"time": times[i], "entry": position["entry"], "exit": exit_price, "profit": profit, "balance_after": balance_local, "reason":"X"})
                if profit>=0: wins+=1
                else: losses+=1
                debug(f"EXIT X idx={i} exit={exit_price:.6f} profit={profit:.8f} newbal={balance_local:.8f}")
                position = None
                continue

    stats = {"initial_balance": initial_balance, "final_balance": round(balance_local,8), "profit_usd": round(balance_local-initial_balance,8),
             "trades": len(trades), "wins": wins, "losses": losses, "win_rate": round((wins/(wins+losses)*100) if (wins+losses)>0 else 0,2)}
    return stats, trades

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def api_status():
    global balance, current_trade, stats
    with balance_lock:
        return jsonify({"balance": round(balance,8), "current_trade": current_trade, "stats": stats, "symbols": SYMBOLS, "trades": trade_history})

@app.route("/api/candles")
def api_candles():
    symbol = request.args.get("symbol", SYMBOLS[0])
    interval = request.args.get("interval", "1m")
    limit = int(request.args.get("limit", KL_LIMIT))
    try:
        data = fetch_klines(symbol, interval=interval, limit=limit)
        return jsonify({"symbol": symbol, "candles": data})
    except Exception as e:
        debug(f"api/candles error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    data = request.form.to_dict() or request.json or {}
    # support CSV upload
    if "csv" in request.files:
        f = request.files["csv"]
        text = f.read().decode("utf-8")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        candles = []
        for i,ln in enumerate(lines):
            if i==0 and "time" in ln.lower() and "open" in ln.lower():
                continue
            parts = ln.split(",")
            if len(parts) < 6: continue
            t = parts[0].strip()
            try:
                if t.isdigit() and len(t)>10:
                    t = int(t)
                else:
                    t = int(datetime.fromisoformat(t).timestamp()*1000)
            except Exception:
                t = int(datetime.utcnow().timestamp()*1000)
            candles.append({"time": int(t), "open": float(parts[1]), "high": float(parts[2]), "low": float(parts[3]), "close": float(parts[4]), "volume": float(parts[5])})
        if not candles:
            return jsonify({"error":"no candles in CSV"}), 400
        initial = float(data.get("initial_balance", INITIAL_BALANCE))
        risk = float(data.get("risk_per_trade", RISK_PER_TRADE))
        stop = float(data.get("stop_loss_pct", STOP_LOSS_PCT))
        stats_out, trades_out = run_backtest(candles, initial_balance=initial, risk_per_trade=risk, stop_loss_pct=stop)
        return jsonify({"stats": stats_out, "trades": trades_out})

    symbol = data.get("symbol", SYMBOLS[0])
    months = int(data.get("months", 1))
    interval = data.get("interval", "1m")
    initial = float(data.get("initial_balance", INITIAL_BALANCE))
    risk = float(data.get("risk_per_trade", RISK_PER_TRADE))
    stop = float(data.get("stop_loss_pct", STOP_LOSS_PCT))

    end = datetime.utcnow()
    start = end - timedelta(days=30*months)

    # fetch pages
    all_candles = []
    start_ms = int(start.timestamp()*1000)
    while True:
        params = {"symbol": symbol, "interval": interval, "limit": 1000, "startTime": start_ms}
        r = requests.get(BINANCE_KLINES, params=params, timeout=20)
        if r.status_code != 200:
            debug(f"binance fetch error {r.status_code} {r.text[:200]}")
            return jsonify({"error":f"binance fetch error {r.status_code}"}), 500
        part = r.json()
        if not part:
            break
        for k in part:
            all_candles.append({"time": int(k[0]), "open":float(k[1]), "high":float(k[2]), "low":float(k[3]), "close":float(k[4]), "volume":float(k[5])})
        if len(part) < 1000:
            break
        start_ms = part[-1][0] + 1
        time.sleep(0.15)

    if not all_candles:
        return jsonify({"error":"no candles retrieved"}), 500

    stats_out, trades_out = run_backtest(all_candles, initial_balance=initial, risk_per_trade=risk, stop_loss_pct=stop)
    return jsonify({"stats": stats_out, "trades": trades_out})

@app.route("/download_trades")
def download_trades():
    try:
        return send_file(TRADE_LOG, as_attachment=True)
    except Exception:
        return jsonify({"error":"no trades yet"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","8000")))
