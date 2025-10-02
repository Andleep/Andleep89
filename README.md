TradeBot (no-pandas) - ready package
-----------------------------------
This project avoids building pandas by using pure-Python indicators.
Files:
- main.py: Flask app + backtester
- templates/index.html, static/app.js: UI
- requirements.txt, runtime.txt, Procfile

Deployment notes:
- On Render use Build command:
  pip install --upgrade pip setuptools wheel && pip install -r requirements.txt
- Start command:
  gunicorn main:app --bind 0.0.0.0:$PORT
