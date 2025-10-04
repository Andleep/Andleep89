# app.py
from flask import Flask, render_template, request, jsonify, send_file
import requests, os, math, io, json
from datetime import datetime, timedelta
from binance.client import Client

app = Flask(__name__, template_folder="templates")

# ---------- Config ----------
DEFAULT_SYMBOL = "ETHUSDT"
BINANCE_API = "https://api.binance.com/api/v3/klines"
# read env
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
USE_TESTNET = os.getenv("BINANCE_USE_TESTNET", "true").lower() in ("1", "true", "yes")

# ---------------------------
def get_binance_client():
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        return None
    client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
    if USE_TESTNET:
        client.API_URL = "https://testnet.binance.vision/api"
    return client

# Fetch klines with optional startTime/endTime in ms or duration param
def fetch_klines(symbol, interval, limit=1000, start_ms=None, end_ms=None):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if start_ms:
        params["startTime"] = int(start_ms)
    if end_ms:
        params["endTime"] = int(end_ms)
    r = requests.get(BINANCE_API, params=params, timeout=20)
    r.raise_for_status()
    raw = r.json()
    candles = []
    for item in raw:
        t = int(item[0])
        candles.append({
            "time": t,
            "time_iso": datetime.utcfromtimestamp(t/1000).isoformat(),
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5])
        })
    return candles

# ---------------------------
# Position sizing (safe)
def safe_position_size(balance, entry_price, sl_price, risk_per_trade=0.01, max_position_pct=0.5):
    risk_amount = balance * risk_per_trade
    stop_dist = abs(entry_price - sl_price)
    if stop_dist <= 0:
        return 0.0
    qty_by_risk = risk_amount / stop_dist
    max_position_value = balance * max_position_pct
    qty_by_value = max_position_value / entry_price if entry_price>0 else 0
    qty = min(qty_by_risk, qty_by_value)
    return max(qty, 0.0)

# ---------------------------
# Simple backtester interface: this uses a strategy module (strategy.py)
import strategy

def run_backtest(candles, initial_balance=10.0, risk_per_trade=0.01, stop_atr_mult=1.0):
    balance = float(initial_balance)
    trades = []
    # state
    pos = None
    for i in range(len(candles)):
        row = candles[i]
        signal = strategy.signal_for_index(candles, i)  # strategy decides buy/sell/none and returns dict
        # check entries
        if pos is None and signal and signal.get("side") in ("buy","sell"):
            entry = row["close"]
            sl = signal.get("stop", entry*0.995)
            qty = safe_position_size(balance, entry, sl, risk_per_trade=risk_per_trade)
            if qty <= 0:
                continue
            pos = {
                "side": signal["side"],
                "entry_index": i,
                "entry_price": entry,
                "stop": sl,
                "qty": qty,
                "balance_at_entry": balance
            }
        # check exits if open
        if pos is not None:
            # exit if strategy says close OR stop hit
            should_close = False
            exit_reason = None
            # stop loss
            if pos["side"] == "buy" and row["low"] <= pos["stop"]:
                should_close = True
                exit_price = pos["stop"]
                exit_reason = "SL"
            elif pos["side"] == "sell" and row["high"] >= pos["stop"]:
                should_close = True
                exit_price = pos["stop"]
                exit_reason = "SL"
            else:
                s2 = strategy.exit_for_index(candles, i, pos)
                if s2:
                    should_close = True
                    exit_price = row["close"]
                    exit_reason = s2.get("reason","X")
            if should_close:
                # compute pnl (for buy: (exit-entry)*qty; for sell: (entry-exit)*qty)
                if pos["side"] == "buy":
                    pnl = (exit_price - pos["entry_price"]) * pos["qty"]
                else:
                    pnl = (pos["entry_price"] - exit_price) * pos["qty"]
                balance = balance + pnl
                trades.append({
                    "time": row["time_iso"],
                    "entry": pos["entry_price"],
                    "exit": exit_price,
                    "profit": pnl,
                    "balance_after": balance,
                    "reason": exit_reason
                })
                pos = None
    return {"start_balance": initial_balance, "end_balance": balance, "trades": trades}

# ---------------------------
# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/klines")
def api_klines():
    symbol = request.args.get("symbol", DEFAULT_SYMBOL)
    interval = request.args.get("interval", "1m")
    period = request.args.get("period", None)  # e.g., "1w", "1m", "6m", or custom start/end
    limit = int(request.args.get("limit", 1000))
    start_ms = None
    end_ms = None
    now_ms = int(datetime.utcnow().timestamp()*1000)
    if period:
        if period == "1w":
            start_ms = now_ms - 7*24*3600*1000
        elif period == "1m":
            start_ms = now_ms - 30*24*3600*1000
        elif period == "6m":
            start_ms = now_ms - 182*24*3600*1000
    # custom start/end
    if request.args.get("start"):
        start_ms = int(request.args.get("start"))
    if request.args.get("end"):
        end_ms = int(request.args.get("end"))
    candles = fetch_klines(symbol, interval, limit=limit, start_ms=start_ms, end_ms=end_ms)
    return jsonify({"candles": candles})

@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    data = request.json or {}
    symbol = data.get("symbol", DEFAULT_SYMBOL)
    interval = data.get("interval", "1m")
    period = data.get("period", "1m")
    initial_balance = float(data.get("initial_balance", 10.0))
    risk_per_trade = float(data.get("risk_per_trade", 0.01))
    # fetch candles
    # use period mapping
    now_ms = int(datetime.utcnow().timestamp()*1000)
    if period == "1w":
        start_ms = now_ms - 7*24*3600*1000
    elif period == "1m":
        start_ms = now_ms - 30*24*3600*1000
    elif period == "6m":
        start_ms = now_ms - 182*24*3600*1000
    else:
        start_ms = now_ms - 30*24*3600*1000
    candles = fetch_klines(symbol, interval, limit=1000, start_ms=start_ms)
    res = run_backtest(candles, initial_balance=initial_balance, risk_per_trade=risk_per_trade)
    return jsonify(res)

@app.route("/api/place_order", methods=["POST"])
def api_place_order():
    payload = request.json or {}
    symbol = payload.get("symbol")
    side = payload.get("side")
    qty = payload.get("quantity")
    client = get_binance_client()
    if client is None:
        return jsonify({"error":"Binance keys not configured in env"}), 400
    try:
        res = client.order_market(symbol=symbol, side=side.upper(), quantity=str(qty))
        return jsonify({"result": res})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download_trades")
def download_trades():
    # example: returns last run trades JSON (for now just empty)
    dummy = {"trades": []}
    return jsonify(dummy)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
