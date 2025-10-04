# strategy.py
# واجهة بسيطة للاستراتيجية: دالتان مركزيتان:
# - signal_for_index(candles, i) => returns {"side":"buy"|"sell", "stop":price} or None
# - exit_for_index(candles, i, pos) => returns {"reason":"X"} or None

def ema(values, period):
    if len(values) < period:
        return None
    k = 2/(period+1)
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
    return sum(trs)/len(trs)

def signal_for_index(candles, i):
    # require some bars
    if i < 20:
        return None
    close = [c["close"] for c in candles[:i+1]]
    ema200 = ema(close, 200)
    ema50 = ema(close, 50)
    if ema200 is None or ema50 is None:
        return None
    # trend filter
    is_up = ema50 > ema200
    is_down = ema50 < ema200
    # kernel-like smoothing: use sma of recent closes
    sma5 = sum(close[-5:]) / 5
    sma8 = sum(close[-8:]) / 8
    # ATR stop
    atr = simple_atr(candles, i, 14) or 0.0
    if is_up and sma5 > sma8:
        # buy signal
        entry = candles[i]["close"]
        stop = entry - max(atr*1.0, entry*0.003)  # ATR-based and minimum %
        return {"side":"buy", "stop": stop}
    if is_down and sma5 < sma8:
        entry = candles[i]["close"]
        stop = entry + max(atr*1.0, entry*0.003)
        return {"side":"sell", "stop": stop}
    return None

def exit_for_index(candles, i, pos):
    # close after 12 bars or opposite signal
    bars_held = i - pos.get("entry_index", i)
    if bars_held >= 12:
        return {"reason":"time"}
    # if opposite signal appears
    s = signal_for_index(candles, i)
    if s and s.get("side") != pos.get("side"):
        return {"reason":"flip"}
    return None
