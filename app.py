# app.py
import os
import csv
import io
import math
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from backtester import Backtester
from indicators import compute_all_indicators

app = Flask(__name__)

# default sample CSV path (included as example)
SAMPLE_CSV = "sample_data/ETHUSDT_1m_sample.csv"  # optional; you can upload CSV via UI

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/run_backtest", methods=["POST"])
def run_backtest():
    """
    Expects JSON form-data:
    - timeframe: '1m','5m','1h' (currently not re-sampling; CSV must match)
    - symbol: string
    - period: 'week'|'month'|'6months' or custom
    - csv_data: optional uploaded file (text)
    - params: dict of strategy params (k, lookback, risk_pct, stop_atr_mult, initial_balance)
    """
    data = request.get_json()
    csv_text = data.get("csv_data")
    params = data.get("params", {})
    initial_balance = float(params.get("initial_balance", 10.0))
    k_neighbors = int(params.get("k_neighbors", 8))
    lookback = int(params.get("lookback", 200))
    stop_atr_mult = float(params.get("stop_atr_mult", 1.0))
    risk_pct = float(params.get("risk_pct", 0.02))  # 2% default risk per trade

    # Read candles: list of dicts with keys: time, open, high, low, close, volume
    candles = []
    if csv_text:
        f = io.StringIO(csv_text)
        reader = csv.DictReader(f)
        for r in reader:
            candles.append({
                "time": int(r.get("time")) if r.get("time") else r.get("datetime"),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r.get("volume", 0.0))
            })
    else:
        # try to load sample data packaged with project
        sample_path = os.path.join(os.path.dirname(__file__), "sample_data", "ETHUSDT_1m_sample.csv")
        if os.path.exists(sample_path):
            with open(sample_path, "r") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    candles.append({
                        "time": int(r.get("time")) if r.get("time") else r.get("datetime"),
                        "open": float(r["open"]),
                        "high": float(r["high"]),
                        "low": float(r["low"]),
                        "close": float(r["close"]),
                        "volume": float(r.get("volume", 0.0))
                    })
        else:
            return jsonify({"error": "no data provided and no sample file found"}), 400

    # compute indicators and run backtest
    indicators = compute_all_indicators(candles)
    bt = Backtester(candles, indicators,
                    k=k_neighbors, lookback=lookback,
                    stop_atr_mult=stop_atr_mult, risk_pct=risk_pct,
                    initial_balance=initial_balance)
    result = bt.run()
    # result contains: trades list, stats, equity_curve (list), markers for plotting
    return jsonify(result)

@app.route("/api/download_trades", methods=["GET"])
def download_trades():
    # If you want to offer CSV download of last run trades, you can implement here.
    return jsonify({"error":"not implemented in this example"}), 404

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
