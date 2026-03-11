// Content script: injects the WebSocket interceptor into the page context.
// Content scripts run in an isolated world and cannot access page JS objects,
// so we inject a <script> tag that loads interceptor.js in the page context.

(function () {
  const script = document.createElement("script");
  script.src = chrome.runtime.getURL("interceptor.js");
  script.onload = function () {
    this.remove();
  };
  (document.head || document.documentElement).appendChild(script);

  // Relay messages from the page context (interceptor.js) to the background
  // service worker via window.postMessage → chrome.runtime.sendMessage.
  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    if (event.data && event.data.type === "WC_MT5_TRADE_SIGNAL") {
      chrome.runtime.sendMessage(event.data.payload);
    }
  });
})();
