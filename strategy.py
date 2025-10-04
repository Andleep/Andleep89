# strategy.py  -- استبدل الملف الحالي بهذا المحتوى
# بسيط، آمن، قابل للتعديل بسرعة

def ema(values, period):
    if len(values) < period:
        return None
    k = 2/(period+1)
    # start with SMA for seed
    ema_val = sum(values[-period:]) / period
    for v in values[-period:]:
        ema_val = v * k + ema_val * (1-k)
    return ema_val

def simple_atr(candles, i, period=14):
    if i < period:
        return 0.0
    trs = []
    for j in range(i-period+1, i+1):
        c = candles[j]
        prev = candles[j-1]["close"] if j-1>=0 else c["close"]
        tr = max(c["high"]-c["low"], abs(c["high"]-prev), abs(c["low"]-prev))
        trs.append(tr)
    return sum(trs)/len(trs) if trs else 0.0

# PARAMETERS (عدلهم كما تريد)
MIN_BARS_REQUIRED = 50
EMA_FAST = 50
EMA_SLOW = 200
ATR_PERIOD = 14
TP_MULT = 1.8   # نسبة الهدف مقابل الستوب (RR = 1 : TP_MULT)
MAX_HOLD_BARS = 12

def signal_for_index(candles, i):
    # نحتاج بيانات كافية
    if i < MIN_BARS_REQUIRED:
        return None
    closes = [c["close"] for c in candles[:i+1]]
    ema_fast = ema(closes, EMA_FAST)
    ema_slow = ema(closes, EMA_SLOW)
    if ema_fast is None or ema_slow is None:
        return None

    # Trend filter
    is_up = ema_fast > ema_slow
    is_down = ema_fast < ema_slow

    # simple momentum: sma crossover
    sma5 = sum(closes[-5:]) / 5
    sma8 = sum(closes[-8:]) / 8

    atr = simple_atr(candles, i, ATR_PERIOD) or 0.0
    entry_price = candles[i]["close"]

    # safety: minimal ATR fallback (percentage)
    min_stop_pct = 0.0025  # 0.25%
    fallback_stop = entry_price * min_stop_pct
    atr_stop = max(atr * 1.0, fallback_stop)

    if is_up and sma5 > sma8:
        # buy
        stop = entry_price - atr_stop
        tp = entry_price + atr_stop * TP_MULT
        return {"side": "buy", "stop": stop, "take": tp}
    if is_down and sma5 < sma8:
        stop = entry_price + atr_stop
        tp = entry_price - atr_stop * TP_MULT
        return {"side": "sell", "stop": stop, "take": tp}
    return None

def exit_for_index(candles, i, pos):
    # pos contains: side, entry_index, entry_price, qty, stop, take
    if pos is None:
        return None
    bars_held = i - pos.get("entry_index", i)
    row = candles[i]
    # Check TP/SL intrabar (conservative: use high/low)
    if pos["side"] == "buy":
        # TP hit?
        if row["high"] >= pos.get("take", 1e18):
            return {"reason": "TP", "price": pos.get("take")}
        # SL hit?
        if row["low"] <= pos.get("stop", 0):
            return {"reason": "SL", "price": pos.get("stop")}
    else:
        if row["low"] <= pos.get("take", -1e18):
            return {"reason": "TP", "price": pos.get("take")}
        if row["high"] >= pos.get("stop", 0):
            return {"reason": "SL", "price": pos.get("stop")}
    # time exit
    if bars_held >= MAX_HOLD_BARS:
        return {"reason": "time", "price": row["close"]}
    # also if opposite signal appears, close
    s = signal_for_index(candles, i)
    if s and s.get("side") != pos.get("side"):
        return {"reason": "flip", "price": row["close"]}
    return None
