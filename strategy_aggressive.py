# strategy_aggressive.py
# نسخة للاختبار: تجعل النمو أسرع لتعطيك رؤية أسرع في المحاكاة
# PARAMETERS (اضبطها في الواجهة/الـ config)
EMA_FAST = 50
EMA_SLOW = 200
ATR_PERIOD = 14
TP_MULT = 2.8        # زيادة الهدف بالنسبة للستوب (اجعلها 2.5-3)
STOP_ATR_MULT = 0.8  # ستوب = ATR * this (أقل من 1 ليكون أقرب)
RISK_PER_TRADE = 0.02  # 2% من الرصيد لكل صفقة (جرب 0.01 ، 0.02 ، 0.05)
MAX_POSITION_PCT = 0.5  # لا تفتح مركز أكبر من 50% من الرصيد (حماية)

MIN_BARS_REQUIRED = 60
MAX_HOLD_BARS = 24

def ema(values, period):
    if len(values) < period:
        return None
    k = 2/(period+1)
    seed = sum(values[-period:]) / period
    e = seed
    for v in values[-period:]:
        e = v * k + e * (1-k)
    return e

def atr(candles, idx, period=ATR_PERIOD):
    if idx < period:
        return 0.0
    trs = []
    for j in range(idx-period+1, idx+1):
        c = candles[j]
        prev = candles[j-1]["close"] if j-1>=0 else c["close"]
        tr = max(c["high"]-c["low"], abs(c["high"]-prev), abs(c["low"]-prev))
        trs.append(tr)
    return sum(trs)/len(trs) if trs else 0.0

def compute_position_size(balance, entry_price, risk_per_trade, stop_price):
    risk_amount = balance * risk_per_trade
    # size in units = risk_amount / (entry - stop) ; protect against zero
    diff = abs(entry_price - stop_price)
    if diff <= 0:
        return 0.0
    size = risk_amount / diff
    # enforce max position value
    max_value = balance * MAX_POSITION_PCT
    if size * entry_price > max_value and entry_price>0:
        size = max_value / entry_price
    return size

def signal_for_index(candles, i):
    if i < MIN_BARS_REQUIRED:
        return None
    closes = [c["close"] for c in candles[:i+1]]
    ema_f = ema(closes, EMA_FAST)
    ema_s = ema(closes, EMA_SLOW)
    if ema_f is None or ema_s is None:
        return None
    is_up = ema_f > ema_s
    is_down = ema_f < ema_s
    sma5 = sum(closes[-5:]) / 5
    sma8 = sum(closes[-8:]) / 8
    price = candles[i]["close"]
    current_atr = atr(candles, i)
    stop_dist = max(current_atr * STOP_ATR_MULT, price * 0.002)  # حافة دنيا 0.2%
    if is_up and sma5 > sma8:
        stop = price - stop_dist
        take = price + stop_dist * TP_MULT
        return {"side":"buy","entry":price,"stop":stop,"take":take}
    if is_down and sma5 < sma8:
        stop = price + stop_dist
        take = price - stop_dist * TP_MULT
        return {"side":"sell","entry":price,"stop":stop,"take":take}
    return None

def exit_for_index(candles, i, pos):
    if not pos:
        return None
    row = candles[i]
    # intrabar check conservative
    if pos["side"] == "buy":
        if row["high"] >= pos["take"]:
            return {"price":pos["take"],"reason":"TP"}
        if row["low"] <= pos["stop"]:
            return {"price":pos["stop"],"reason":"SL"}
    else:
        if row["low"] <= pos["take"]:
            return {"price":pos["take"],"reason":"TP"}
        if row["high"] >= pos["stop"]:
            return {"price":pos["stop"],"reason":"SL"}
    if i - pos["entry_index"] >= MAX_HOLD_BARS:
        return {"price":row["close"],"reason":"time"}
    # flip
    s = signal_for_index(candles, i)
    if s and s["side"] != pos["side"]:
        return {"price":row["close"],"reason":"flip"}
    return None
