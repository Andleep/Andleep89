// UI logic
const symbolSelect = document.getElementById("symbolSelect");
const monthsSelect = document.getElementById("monthsSelect");
const intervalSelect = document.getElementById("intervalSelect");
const runBtn = document.getElementById("runBtn");
const uploadCsvBtn = document.getElementById("uploadCsv");
const csvFile = document.getElementById("csvFile");
const statsDiv = document.getElementById("stats");
const tradesTbody = document.querySelector("#tradesTable tbody");
const balanceEl = document.getElementById("balance");
let chart;

async function loadSymbols(){
  const res = await fetch("/api/status");
  const j = await res.json();
  const syms = j.symbols || ["ETHUSDT"];
  symbolSelect.innerHTML = syms.map(s=>`<option value="${s}">${s}</option>`).join("");
}
loadSymbols();

runBtn.onclick = async ()=>{
  const symbol = symbolSelect.value;
  const months = parseInt(monthsSelect.value);
  const interval = intervalSelect.value;
  statsDiv.innerText = "جاري المحاكاة...";
  let body = {symbol, months, interval, initial_balance:10.0};
  if(months === 0){
    alert("اختر ملف CSV ثم اضغط رفع CSV ثم نفّذ المحاكاة.");
    return;
  }
  const res = await fetch("/api/backtest", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body)
  });
  const data = await res.json();
  if(data.error){ statsDiv.innerText = "خطأ: " + data.error; return; }
  const stats = data.stats;
  const trades = data.trades;
  statsDiv.innerHTML = `البداية $${stats.initial_balance} — النهاية $${stats.final_balance} — صفقات: ${stats.trades} — فوز: ${stats.wins} — خسارة: ${stats.losses} — نسبة فوز: ${stats.win_rate}%`;
  balanceEl.innerText = `الرصيد: $${stats.final_balance}`;
  updateTrades(trades);
  const c = await fetch(`/api/candles?symbol=${symbol}&limit=500&interval=${interval}`).then(r=>r.json());
  if(!c.error) buildChart(c.candles);
};

uploadCsvBtn.onclick = ()=> csvFile.click();
csvFile.onchange = async (e)=>{
  const f = e.target.files[0];
  if(!f) return;
  const fd = new FormData();
  fd.append("csv", f);
  const res = await fetch("/api/backtest", {method:"POST", body: fd});
  const data = await res.json();
  if(data.error){ alert("Upload error: "+data.error); return; }
  alert("CSV uploaded and simulated. See results in UI.");
  const stats = data.stats;
  const trades = data.trades;
  statsDiv.innerHTML = `البداية $${stats.initial_balance} — النهاية $${stats.final_balance} — صفقات: ${stats.trades}`;
  updateTrades(trades);
};

function updateTrades(trades){
  tradesTbody.innerHTML = trades.slice().reverse().map(t=>`<tr>
    <td>${new Date(t.time).toLocaleString()}</td>
    <td>${t.entry?.toFixed(6)||''}</td>
    <td>${t.exit?.toFixed(6)||''}</td>
    <td class="${t.profit>=0?'green':'red'}">${t.profit?.toFixed(6)||''}</td>
    <td>${t.balance_after?.toFixed(6)||''}</td>
    <td>${t.reason||''}</td>
  </tr>`).join('');
}

function buildChart(candles){
  const ds = candles.map(c=>({x:new Date(c.time), o:c.open, h:c.high, l:c.low, c:c.close}));
  const ctx = document.getElementById("chart").getContext("2d");
  if(chart) chart.destroy();
  chart = new Chart(ctx, {
    type:'candlestick',
    data:{datasets:[{label:'Price', data:ds}]},
    options:{plugins:{legend:{display:false}}, scales:{x:{time:{unit:'minute'}}}}
  });
}
