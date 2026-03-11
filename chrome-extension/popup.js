const MIDDLEWARE_URL = "http://127.0.0.1:5000";

async function checkStatus() {
  const statusEl = document.getElementById("status");
  const dotEl = document.getElementById("statusDot");
  const textEl = document.getElementById("statusText");

  try {
    const resp = await fetch(`${MIDDLEWARE_URL}/api/health`, {
      signal: AbortSignal.timeout(3000),
    });
    if (resp.ok) {
      const data = await resp.json();
      statusEl.className = "status connected";
      dotEl.className = "dot green";
      textEl.textContent = `Middleware online — MT5 ${data.mt5_connected ? "connected" : "disconnected"}`;

      // Update stats
      if (data.stats) {
        document.getElementById("signalCount").textContent =
          data.stats.signals_received || 0;
        document.getElementById("orderCount").textContent =
          data.stats.orders_executed || 0;
      }
    } else {
      throw new Error("Not OK");
    }
  } catch {
    statusEl.className = "status disconnected";
    dotEl.className = "dot red";
    textEl.textContent = "Middleware offline";
  }
}

async function loadLog() {
  try {
    const resp = await fetch(`${MIDDLEWARE_URL}/api/log?limit=10`, {
      signal: AbortSignal.timeout(3000),
    });
    if (resp.ok) {
      const data = await resp.json();
      const logEl = document.getElementById("log");
      if (data.entries && data.entries.length > 0) {
        logEl.innerHTML = data.entries
          .map((entry) => {
            const cls =
              entry.side === "BUY"
                ? "buy"
                : entry.side === "SELL"
                  ? "sell"
                  : entry.type === "POSITION_CLOSE"
                    ? "close"
                    : "";
            const time = new Date(entry.timestamp).toLocaleTimeString();
            return `<div class="entry ${cls}">${time} ${entry.type} ${entry.symbol} ${entry.side || ""} ${entry.quantity || ""}</div>`;
          })
          .join("");

        // Update last signal
        const last = data.entries[0];
        document.getElementById("lastSignal").textContent =
          new Date(last.timestamp).toLocaleTimeString();
      }
    }
  } catch {
    // Ignore
  }
}

checkStatus();
loadLog();
setInterval(checkStatus, 5000);
setInterval(loadLog, 3000);
