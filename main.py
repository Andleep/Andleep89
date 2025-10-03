# main.py
import os
import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from strategy import generate_signals
import requests
import numpy as np
import csv
from io import StringIO

app = Flask(__name__, static_folder="static", template_folder="templates")

# config (تعديل سهل)
INITIAL_BALANCE = 10.0
POSITION_SIZE_PCT = 0.03      # يخاطر 3% من الرصيد في كل صفقة (قابل للتعديل)
MAX_POSITION_PCT = 0.25
STOP_LOSS_PCT = 0.01          # 1% stop
TAKE_PROFIT_PCT = 0.02        # 2% take profit (اختياري)
EMA_SHORT = 20
EMA_LONG = 50
RSI_PERIOD = 14
VOLUME_MULTIPLIER = 1.2

# in-memory state
state = {
    "balance": INITIAL_BALANCE,
    "trades": [],    # قائمة الصفقات (history)
    "candles": [],   # بيانات الشموع الحالية المستخدمة للعروض
    "running": False
}

def parse_csv_candles(text):
    """
    نتوقع ملف CSV بعناوين: time,open,high,low,close,volume
    time can be ISO or ms epoch.
    """
    reader = csv.DictReader(StringIO(text))
    out = []
    for row in reader:
        try:
            t = row.get('time') or row.get('timestamp') or row.get('Date') or row.get('date')
            # حاول تحويل الى int ms أو الى ISO
            try:
                if '.' in t or len(t) > 12:
                    # ISO
                    dt = t
                else:
                    # epoch seconds/millis
                    v = int(t)
                    if v > 1e12:
                        dt = int(v)
                    else:
                        dt = int(v)*1000
                # we will keep time as int ms if numeric
            except Exception:
                dt = t
            c = {
                "time": dt,
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": float(row.get('volume', 0.0))
            }
            out.append(c)
        except Exception:
            continue
    return out

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/upload_csv", methods=["POST"])
def upload_csv():
    f = request.files.get("file")
    if not f:
        return jsonify({"error":"no file"}), 400
    text = f.stream.read().decode('utf-8')
    candles = parse_csv_candles(text)
    if not candles:
        return jsonify({"error":"no valid candles parsed"}), 400
    # keep latest N candles
    state['candles'] = candles[-1000:]
    state['trades'] = []
    state['balance'] = INITIAL_BALANCE
    return jsonify({"status":"ok", "candles": len(state['candles'])})

@app.route("/api/load_sample")
def load_sample():
    # تحميل مثال صغير من GitHub gist (لو فشل استخدم بيانات مولدة)
    url = "https://raw.githubusercontent.com/Andleep/Trend-andleep89/main/sample_eth.csv"
    try:
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        state['candles'] = parse_csv_candles(r.text)
    except Exception:
        # generate synthetic sinusoidal data as fallback
        now = int(time.time()*1000)
        candles = []
        price = 4000.0
        for i in range(500):
            o = price + np.random.randn()*3
            c = o + np.random.randn()*2
            h = max(o,c) + abs(np.random.randn()*2)
            l = min(o,c) - abs(np.random.randn()*2)
            candles.append({"time": now - (500-i)*60000, "open":o,"high":h,"low":l,"close":c,"volume":abs(np.random.randn()*1000)})
            price = c
        state['candles'] = candles
    state['trades'] = []
    state['balance'] = INITIAL_BALANCE
    return jsonify({"status":"ok", "candles": len(state['candles'])})

@app.route("/api/run_backtest", methods=["POST"])
def run_backtest():
    """
    Runs backtest on currently loaded candles using the strategy.generate_signals.
    Returns trades list and final balance.
    """
    cfg = {
        "ema_short": int(request.json.get("ema_short", EMA_SHORT)),
        "ema_long": int(request.json.get("ema_long", EMA_LONG)),
        "rsi_period": int(request.json.get("rsi_period", RSI_PERIOD)),
        "volume_multiplier": float(request.json.get("volume_multiplier", VOLUME_MULTIPLIER))
    }
    candles = state.get('candles', [])
    if not candles:
        return jsonify({"error":"no candles loaded"}), 400

    signals = generate_signals(candles, cfg)

    balance = INITIAL_BALANCE
    current = None  # current trade dict
    trades = []

    for i in range(len(candles)):
        sig = signals[i]
        price = candles[i]['close']
        # check stoploss for open trade
        if current is not None:
            # check SL
            if price <= current['stop_price']:
                # exit at current price
                proceeds = current['qty'] * price
                profit = proceeds - current['cost']
                balance += profit
                trades.append({
                    "time": candles[i]['time'], "symbol": "SIM",
                    "entry": current['entry'], "exit": price,
                    "profit": profit, "balance_after": balance, "reason":"SL"
                })
                current = None
                continue
        # handle signal
        if sig == "ENTER" and current is None:
            # position sizing (value)
            desired_value = balance * POSITION_SIZE_PCT
            desired_value = min(desired_value, balance * MAX_POSITION_PCT)
            if desired_value < 1e-8:
                continue
            qty = desired_value / price
            cost = qty * price
            stop_price = price * (1 - STOP_LOSS_PCT)
            current = {"entry":price, "qty":qty, "cost":cost, "stop_price":stop_price}
            continue
        if sig == "EXIT_X" and current is not None:
            proceeds = current['qty'] * price
            profit = proceeds - current['cost']
            balance += profit
            trades.append({"time": candles[i]['time'], "symbol":"SIM", "entry": current['entry'], "exit": price, "profit":profit, "balance_after":balance, "reason":"X"})
            current = None
            continue

    # force close last open trade at last candle if still open
    if current is not None:
        price = candles[-1]['close']
        proceeds = current['qty'] * price
        profit = proceeds - current['cost']
        balance += profit
        trades.append({"time": candles[-1]['time'], "symbol":"SIM", "entry": current['entry'], "exit": price, "profit":profit, "balance_after":balance, "reason":"CLOSE"})

    # save to state for frontend display
    state['trades'] = trades
    state['balance'] = balance

    return jsonify({
        "final_balance": balance,
        "trades_count": len(trades),
        "trades": trades
    })

@app.route("/api/status")
def api_status():
    # return basic status and last N candles
    return jsonify({
        "balance": state['balance'],
        "trades": state['trades'][-200:],
        "candles": state['candles'][-500:]
    })

@app.route("/api/download_trades")
def download_trades():
    # generate CSV
    si = StringIO()
    w = csv.writer(si)
    w.writerow(["time","entry","exit","profit","balance_after","reason"])
    for t in state['trades']:
        w.writerow([t.get('time'), t.get('entry'), t.get('exit'), t.get('profit'), t.get('balance_after'), t.get('reason')])
    si.seek(0)
    return app.response_class(si.getvalue(), mimetype='text/csv',
                              headers={"Content-Disposition":"attachment;filename=trades.csv"})

if __name__ == "__main__":
    # for local debug
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8000)), debug=True)
