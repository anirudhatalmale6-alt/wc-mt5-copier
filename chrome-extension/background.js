// Background service worker: receives trade signals from the content script
// and can perform additional processing or logging.

const MIDDLEWARE_URL = "http://127.0.0.1:5000";

// Listen for messages from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type) {
    console.log("[WC-MT5 BG] Received signal:", message.type, message.symbol);

    // Update badge to show activity
    chrome.action.setBadgeText({ text: "ON" });
    chrome.action.setBadgeBackgroundColor({ color: "#22c55e" });

    // Flash badge on new signals
    if (
      message.type === "ORDER" ||
      message.type === "POSITION_OPEN" ||
      message.type === "POSITION_CLOSE"
    ) {
      flashBadge(message.type);
    }
  }
  return false;
});

function flashBadge(signalType) {
  const color =
    signalType === "POSITION_CLOSE"
      ? "#ef4444"
      : signalType === "POSITION_OPEN"
        ? "#22c55e"
        : "#3b82f6";
  const text =
    signalType === "POSITION_CLOSE"
      ? "CLS"
      : signalType === "POSITION_OPEN"
        ? "NEW"
        : "ORD";

  chrome.action.setBadgeText({ text: text });
  chrome.action.setBadgeBackgroundColor({ color: color });

  setTimeout(() => {
    chrome.action.setBadgeText({ text: "ON" });
    chrome.action.setBadgeBackgroundColor({ color: "#22c55e" });
  }, 3000);
}

// Check middleware health periodically
async function checkMiddleware() {
  try {
    const response = await fetch(`${MIDDLEWARE_URL}/api/health`, {
      method: "GET",
      signal: AbortSignal.timeout(3000),
    });
    if (response.ok) {
      chrome.action.setBadgeText({ text: "ON" });
      chrome.action.setBadgeBackgroundColor({ color: "#22c55e" });
    } else {
      chrome.action.setBadgeText({ text: "ERR" });
      chrome.action.setBadgeBackgroundColor({ color: "#ef4444" });
    }
  } catch {
    chrome.action.setBadgeText({ text: "OFF" });
    chrome.action.setBadgeBackgroundColor({ color: "#6b7280" });
  }
}

// Check every 30 seconds
setInterval(checkMiddleware, 30000);
checkMiddleware();
