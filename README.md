TradeBot — Simulation + Paper Trading (Testnet)
------------------------------------------------
ملف المشروع هذا يعطيك:
- web UI لعرض الشموع ونتائج backtest (week/month/6months/custom)
- ملف strategy.py منفصل لتعديل الاستراتيجية بسهولة
- paper trading عبر Binance Testnet إذا ضبطت مفاتيحك كـ env vars

تنصيب محلي:
1. python -m venv .venv
2. source .venv/bin/activate
3. pip install -r requirements.txt
4. export BINANCE_USE_TESTNET=true
   export BINANCE_API_KEY=...
   export BINANCE_API_SECRET=...
5. gunicorn app:app

ملاحظة أمان: لا تضع مفاتيحك في الكود. استخدم متغيرات البيئة.
