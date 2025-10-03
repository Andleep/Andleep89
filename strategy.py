# strategy.py
# مؤشرات وبرنامج اشارات مبني بدون pandas (باستخدام قائمة و numpy)
import numpy as np

def ema_list(values, span):
    """
    حساب EMA على قائمة floats، إرجاع قائمة بنفس الطول (القيم الأولى None حتى تتوفر البيانات).
    """
    values = np.array(values, dtype=float)
    alpha = 2 / (span + 1)
    out = [None] * len(values)
    ema = None
    for i, v in enumerate(values):
        if i == 0:
            ema = v
        else:
            ema = alpha * v + (1 - alpha) * ema
        out[i] = float(ema)
    return out

def rsi_list(values, period=14):
    """
    حساب RSI (بسيط) على قائمة أسعار الإغلاق.
    """
    deltas = np.diff(values)
    up = np.where(deltas > 0, deltas, 0.0)
    down = np.where(deltas < 0, -deltas, 0.0)
    rsis = [None]  # first index has no rsi
    # compute first avg gain/loss as simple mean over first `period` deltas (if available)
    avg_gain = None
    avg_loss = None
    for i in range(1, len(values)):
        window_up = up[max(0, i-period):i]
        window_down = down[max(0, i-period):i]
        if len(window_up) < 1:
            rsis.append(None)
            continue
        ag = window_up.mean()
        al = window_down.mean()
        if al == 0 and ag == 0:
            rsis.append(50.0)
        else:
            rs = (ag / (al + 1e-12))
            rsi = 100 - (100 / (1 + rs))
            rsis.append(float(rsi))
    return rsis

def generate_signals(candles, config):
    """
    candles: list of dicts each {time, open, high, low, close, volume}
    config: dict with ema_short, ema_long, rsi_period, volume_multiplier, stop_loss_pct
    Return: list of trades decisions per candle: "ENTER","EXIT_SL","EXIT_X", or None
    """
    closes = [c['close'] for c in candles]
    volumes = [c['volume'] for c in candles]
    ema_s = ema_list(closes, config.get('ema_short', 20))
    ema_l = ema_list(closes, config.get('ema_long', 50))
    rsi = rsi_list(closes, config.get('rsi_period', 14))

    signals = [None] * len(candles)

    # average volume sliding
    vol_arr = np.array(volumes, dtype=float)
    avg_vol = np.convolve(vol_arr, np.ones(20)/20, mode='same')

    for i in range(2, len(candles)):
        # use candle i-1 as closed candle signal (like typical backtest)
        idx = i-1
        if ema_s[idx] is None or ema_l[idx] is None or rsi[idx] is None:
            continue
        s_now = ema_s[idx]
        l_now = ema_l[idx]
        s_prev = ema_s[idx-1]
        l_prev = ema_l[idx-1]

        cross_up = (s_prev <= l_prev) and (s_now > l_now)
        cross_down = (s_prev >= l_prev) and (s_now < l_now)

        vol_ok = volumes[idx] > (avg_vol[idx] * config.get('volume_multiplier', 1.2))
        rsi_ok = (rsi[idx] > 25) and (rsi[idx] < 75)

        if cross_up and vol_ok and rsi_ok:
            signals[idx] = "ENTER"
        elif cross_down:
            signals[idx] = "EXIT_X"
        # stop loss handled during simulation loop by comparing price to stop_price

    return signals
