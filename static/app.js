// static/app.js
document.addEventListener("DOMContentLoaded", function(){
  const loadSampleBtn = document.getElementById("load_sample");
  const csvfile = document.getElementById("csvfile");
  const chartDiv = document.getElementById("chart");
  const balanceEl = document.getElementById("balance");
  const tradesCountEl = document.getElementById("trades_count");
  const winsEl = document.getElementById("wins");
  const lossesEl = document.getElementById("losses");
  const tradesTableBody = document.querySelector("#trades_table tbody");

  function arrayToCSV(rows) {
    if (!rows || !rows.length) return "";
    const keys = Object.keys(rows[0]);
    const lines = [keys.join(",")];
    for (const r of rows) {
      lines.push(keys.map(k => r[k]).join(","));
    }
    return lines.join("\n");
  }

  function runBacktestWithCSV(csvText) {
    const payload = {
      csv_data: csvText,
      params: {
        initial_balance: parseFloat(document.getElementById("initial_balance").value),
        k_neighbors: parseInt(document.getElementById("k").value),
        lookback: parseInt(document.getElementById("lookback").value),
        stop_atr_mult: parseFloat(document.getElementById("stop_atr").value),
        risk_pct: parseFloat(document.getElementById("risk_pct").value)
      }
    };
    fetch("/api/run_backtest", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    }).then(r => r.json()).then(drawResults).catch(e => alert("Error: "+e));
  }

  loadSampleBtn.addEventListener("click", function(){
    // fetch sample server-side via run_backtest without CSV_text (server loads sample file)
    runBacktestWithCSV(null);
  });

  csvfile.addEventListener("change", function(e){
    const f = e.target.files[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = function(ev){
      const txt = ev.target.result;
      runBacktestWithCSV(txt);
    };
    reader.readAsText(f);
  });

  function drawResults(result){
    if (result.error){
      alert(result.error);
      return;
    }
    // build candlestick from CSV used on server (server used sample file or csv provided).
    // The server didn't return full candle series; but equity curve is returned with timestamps.
    // For better plotting, we will reuse server-sent trades and equity for now.

    // show stats
    balanceEl.textContent = parseFloat(result.final_balance).toFixed(8);
    tradesCountEl.textContent = result.trades.length;
    winsEl.textContent = result.stats.wins;
    lossesEl.textContent = result.stats.losses;

    // populate trades table
    tradesTableBody.innerHTML = "";
    for (const t of result.trades.slice(-200).reverse()){
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${t.time_str||t.time}</td><td>${t.entry}</td><td>${t.exit}</td><td>${t.profit}</td><td>${t.balance_after}</td><td>${t.reason}</td>`;
      tradesTableBody.appendChild(tr);
    }

    // draw equity curve
    const x = result.equity.map(e => new Date(e.time));
    const y = result.equity.map(e => e.equity);
    const trace = { x:x, y:y, type:"scatter", name:"Equity" };
    Plotly.newPlot(chartDiv, [trace], {margin:{t:30}});
  }
});
