# TradeBot — Simulation (Pure Python, no pandas)

### Quick start (locally)
1. Create virtualenv with Python 3.11
2. `pip install -r requirements.txt`
3. `python app.py` and open `http://127.0.0.1:8000`

### Deploy on Render
- Add repo to Render.
- In Render service settings:
  - Build command: `pip install -r requirements.txt`
  - Start command: `gunicorn app:app`
  - Runtime: ensure Python 3.11 (`runtime.txt` present)
- Upload sample CSV or use UI to upload.

### CSV format expected
CSV header: `time,open,high,low,close,volume`
- time can be epoch milliseconds or datetime string
- sample file path (optional): `sample_data/ETHUSDT_1m_sample.csv`

### About strategy
- This project implements a simplified Lorentzian-KNN style classifier using RSI/ADX/CCI features.
- Position sizing: risk-based using ATR stop and `risk_pct`.
- Only LONG trades implemented (can be extended).
- All trading is simulated; to enable live trading with Binance you'll need to:
  - Add Binance REST API client (python-binance or ccxt)
  - Provide API key & secret in environment variables
  - Use Binance Testnet first
  - Add endpoint to switch from simulation to live/paper trading

### Notes
- This is a starting point. The indicator you pasted (Pine script) is complex — I translated the core idea (features + Lorentzian distance KNN) into a runnable Python backtester.
- For heavy ML or greater realism, you can later add numpy/pandas and choose a Render instance with Python 3.10/3.11 and compiled wheels support.
