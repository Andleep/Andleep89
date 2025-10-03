// static/app.js
let chart = null;

function isoTime(t){
  try{
    // if t is ms int
    if(typeof t === "number") return new Date(t).toLocaleString();
    if(!isNaN(Number(t))) return new Date(Number(t)).toLocaleString();
    return t;
  }catch(e){return t;}
}

async function fetchStatus(){
  const r = await fetch("/api/status");
  const j = await r.json();
  document.getElementById("balance").textContent = (Math.round((j.balance + Number.EPSILON)*100000000)/100000000).toString();
  drawChart(j.candles, j.trades);
  populateTrades(j.trades);
}

function drawChart(candles, trades){
  const labels = candles.map(c=> isoTime(c.time));
  const closes = candles.map(c=> c.close);
  // trade markers
  const buys = trades.filter(t=> t.profit >=0 || t.reason === "CLOSE").map(t=> ({x: isoTime(t.time), y: t.exit}));
  const sells = trades.filter(t=> t.profit < 0 && t.reason !== "CLOSE").map(t=> ({x: isoTime(t.time), y: t.exit}));
  const ctx = document.getElementById('priceChart').getContext('2d');
  if(chart) chart.destroy();
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        { label: 'Close', data: closes, borderColor:'#2b8aef', tension:0.1, pointRadius:0 },
        { label: 'Buys', data: buys.map(p=> p.y), pointBackgroundColor:'green', type:'scatter', showLine:false },
        { label: 'Sells', data: sells.map(p=> p.y), pointBackgroundColor:'red', type:'scatter', showLine:false }
      ]
    },
    options: {
      interaction:{mode:'index'},
      plugins:{legend:{display:true}},
      scales:{ x:{ display:true } }
    }
  });
}

function populateTrades(trades){
  const tbody = document.querySelector("#trades-table tbody");
  tbody.innerHTML = "";
  trades.slice().reverse().forEach(t=>{
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${isoTime(t.time)}</td><td>${t.entry}</td><td>${t.exit}</td><td>${t.profit}</td><td>${t.balance_after}</td><td>${t.reason}</td>`;
    tbody.appendChild(tr);
  });
}

document.getElementById("load-sample").addEventListener("click", async ()=>{
  await fetch("/api/load_sample");
  await fetchStatus();
});

document.getElementById("run-backtest").addEventListener("click", async ()=>{
  const body = {
    ema_short: 20,
    ema_long: 50,
    rsi_period: 14,
    volume_multiplier: 1.2
  };
  const r = await fetch("/api/run_backtest", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body)
  });
  const j = await r.json();
  alert("Backtest finished. Final balance: "+ j.final_balance.toFixed(8));
  await fetchStatus();
});

document.getElementById("file").addEventListener("change", async (ev)=>{
  const f = ev.target.files[0];
  if(!f) return;
  const form = new FormData();
  form.append("file", f);
  const r = await fetch("/api/upload_csv", { method:"POST", body: form });
  const j = await r.json();
  if(j.error) alert("Upload error: "+ j.error);
  else {
    alert("Uploaded "+ j.candles +" candles.");
    await fetchStatus();
  }
});

// initial
fetchStatus();
setInterval(fetchStatus, 5000);
