# indicators.py
import math

def sma(values, period):
    out = []
    s = 0.0
    window = []
    for i,v in enumerate(values):
        window.append(v)
        s += v
        if len(window) > period:
            s -= window.pop(0)
        if len(window) == period:
            out.append(s/period)
        else:
            out.append(0.0)
    return out

def ema(values, period):
    out = []
    k = 2/(period+1)
    ema_prev = None
    for v in values:
        if ema_prev is None:
            ema_prev = v
        else:
            ema_prev = v * k + ema_prev * (1-k)
        out.append(ema_prev)
    return out

def compute_rsi(close, period=14):
    out = []
    gains = []
    losses = []
    for i in range(len(close)):
        if i==0:
            out.append(50.0)
            continue
        delta = close[i] - close[i-1]
        gains.append(max(delta,0))
        losses.append(max(-delta,0))
        if i < period:
            out.append(50.0)
        else:
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period
            rs = avg_gain / (avg_loss+1e-12)
            rsi = 100 - (100 / (1 + rs))
            out.append(rsi)
    return out

def compute_atr(high, low, close, period=14):
    out = []
    trs = []
    for i in range(len(close)):
        if i==0:
            tr = high[i] - low[i]
        else:
            tr = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
        trs.append(tr)
        if i < period:
            out.append(sum(trs)/len(trs))
        else:
            # simple rolling average
            out.append(sum(trs[-period:]) / period)
    return out

def compute_cci(high, low, close, period=20):
    out = []
    tp_list = []
    for i in range(len(close)):
        tp = (high[i]+low[i]+close[i])/3
        tp_list.append(tp)
        if i < period-1:
            out.append(0.0)
        else:
            sma_tp = sum(tp_list[-period:]) / period
            mean_dev = sum([abs(x - sma_tp) for x in tp_list[-period:]]) / period
            cci = (tp - sma_tp) / (0.015 * (mean_dev + 1e-12))
            out.append(cci)
    return out

def compute_adx(high, low, close, period=14):
    # simplified ADX using directional movement
    tr = []
    pdm = []
    ndm = []
    for i in range(len(close)):
        if i==0:
            tr.append(high[i]-low[i])
            pdm.append(0)
            ndm.append(0)
            continue
        curr_tr = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
        tr.append(curr_tr)
        up = high[i] - high[i-1]
        down = low[i-1] - low[i]
        pdm.append(up if (up>down and up>0) else 0)
        ndm.append(down if (down>up and down>0) else 0)
    # smooth
    atr = []
    for i in range(len(tr)):
        if i < period:
            atr.append(sum(tr[:i+1])/(i+1))
        else:
            atr.append(sum(tr[i-period+1:i+1]) / period)
    pdi = []
    ndi = []
    for i in range(len(tr)):
        if atr[i] == 0:
            pdi.append(0); ndi.append(0)
        else:
            pdi.append(100 * (sum(pdm[max(0,i-period+1):i+1]) / atr[i]))
            ndi.append(100 * (sum(ndm[max(0,i-period+1):i+1]) / atr[i]))
    dx = []
    for i in range(len(tr)):
        denom = pdi[i] + ndi[i]
        if denom == 0:
            dx.append(0)
        else:
            dx.append(100 * abs(pdi[i] - ndi[i]) / denom)
    adx = []
    for i in range(len(dx)):
        if i < period:
            adx.append(sum(dx[:i+1])/(i+1))
        else:
            adx.append(sum(dx[i-period+1:i+1]) / period)
    return adx

def compute_all_indicators(candles):
    close = [c['close'] for c in candles]
    high = [c['high'] for c in candles]
    low = [c['low'] for c in candles]
    rsi = compute_rsi(close, period=14)
    atr = compute_atr(high, low, close, period=14)
    cci = compute_cci(high, low, close, period=20)
    adx = compute_adx(high, low, close, period=14)
    return {'rsi': rsi, 'atr': atr, 'cci': cci, 'adx': adx}
