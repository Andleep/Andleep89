# backtester.py
import math
from datetime import datetime
from statistics import mean
from collections import deque

# We expect indicators dict to contain lists of same length as candles:
# indicators = { 'rsi': [...], 'adx': [...], 'cci': [...], 'atr': [...], ... }

class Backtester:
    def __init__(self, candles, indicators, k=8, lookback=200, stop_atr_mult=1.0, risk_pct=0.02, initial_balance=10.0):
        self.candles = candles
        self.ind = indicators
        self.k = k
        self.lookback = lookback
        self.stop_atr_mult = stop_atr_mult
        self.risk_pct = risk_pct
        self.initial_balance = initial_balance

    def lorentzian_distance(self, i, j, features):
        # features: dict of lists; i and j are indices into series (0..n-1)
        s = 0.0
        for name in features:
            a = features[name][i]
            b = features[name][j]
            s += math.log(1 + abs(a - b))
        return s

    def predict_knn(self, idx):
        # predict direction at idx using previous bars up to lookback
        n = len(self.candles)
        features = { 'rsi': self.ind['rsi'], 'adx': self.ind['adx'], 'cci': self.ind['cci'] }
        distances = []
        start = max(0, idx - self.lookback)
        for j in range(start, idx):
            d = self.lorentzian_distance(idx, j, features)
            distances.append((d, j))
        distances.sort(key=lambda x: x[0])
        if not distances:
            return 0
        k = min(self.k, len(distances))
        votes = 0
        for _, j in distances[:k]:
            # label: compare close after 4 bars vs current close (as in pine): simple future return
            future_idx = j + 4
            if future_idx < len(self.candles):
                ret = self.candles[future_idx]['close'] - self.candles[j]['close']
                votes += (1 if ret > 0 else -1 if ret < 0 else 0)
        return 1 if votes > 0 else -1 if votes < 0 else 0

    def run(self):
        balance = self.initial_balance
        equity_curve = []
        trades = []
        position = None  # dict with entry_price, qty, stop_price, entry_index
        stats = {"trades":0, "wins":0, "losses":0, "profit_usd":0.0}

        n = len(self.candles)
        for i in range(50, n-4):  # start after some warmup
            signal = self.predict_knn(i)
            price = self.candles[i]['close']
            atr = self.ind['atr'][i] if self.ind['atr'][i] > 0 else 0.0

            # entry logic: only one position at a time (long-only for simplicity)
            if position is None and signal == 1:
                # position sizing by risk_pct and ATR stop
                if atr <= 0:
                    # fallback small size
                    qty = balance / price
                    stop_price = price * 0.99
                else:
                    stop_distance = self.stop_atr_mult * atr
                    risk_amount = balance * self.risk_pct
                    qty = risk_amount / stop_distance if stop_distance>0 else balance/price
                    # ensure qty not huge
                    if qty * price > balance:
                        qty = balance / price
                    stop_price = price - stop_distance
                position = {
                    "side":"LONG",
                    "entry_price":price,
                    "qty":qty,
                    "stop_price":stop_price,
                    "entry_index":i
                }
            # manage open position
            if position is not None:
                last_price = price
                # stop loss check
                if last_price <= position["stop_price"]:
                    # exit
                    proceeds = position["qty"] * last_price
                    cost = position["qty"] * position["entry_price"]
                    profit = proceeds - cost
                    balance = proceeds  # compounding
                    trades.append({
                        "time": self.candles[i]['time'],
                        "entry": position["entry_price"],
                        "exit": last_price,
                        "profit": profit,
                        "balance_after": balance,
                        "reason": "SL"
                    })
                    stats["trades"] += 1
                    if profit >= 0: stats["wins"] += 1
                    else: stats["losses"] += 1
                    position = None
                else:
                    # exit condition from model: if signal flips to -1 then exit
                    if signal == -1:
                        proceeds = position["qty"] * last_price
                        cost = position["qty"] * position["entry_price"]
                        profit = proceeds - cost
                        balance = proceeds
                        trades.append({
                            "time": self.candles[i]['time'],
                            "entry": position["entry_price"],
                            "exit": last_price,
                            "profit": profit,
                            "balance_after": balance,
                            "reason": "X"
                        })
                        stats["trades"] += 1
                        if profit >= 0: stats["wins"] += 1
                        else: stats["losses"] += 1
                        position = None
            equity_curve.append({"time": self.candles[i]['time'], "equity": balance})

        stats["profit_usd"] = round(balance - self.initial_balance, 8)
        # convert trade times to human-readable
        for t in trades:
            try:
                if isinstance(t["time"], (int, float)):
                    t["time_str"] = datetime.utcfromtimestamp(t["time"]/1000).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    t["time_str"] = str(t["time"])
            except Exception:
                t["time_str"] = str(t["time"])

        return {
            "initial_balance": self.initial_balance,
            "final_balance": balance,
            "trades": trades,
            "stats": stats,
            "equity": equity_curve
        }
