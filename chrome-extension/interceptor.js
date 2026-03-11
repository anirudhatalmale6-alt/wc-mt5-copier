// Interceptor: runs in the PAGE context (injected via injector.js).
// Monkey-patches the native WebSocket to capture trade-related messages
// from WealthCharts and forwards them to the content script.

(function () {
  "use strict";

  const MIDDLEWARE_URL = "http://127.0.0.1:5000";

  // Keep reference to original WebSocket
  const OriginalWebSocket = window.WebSocket;

  // Track last known state per order to avoid duplicate signals
  const orderStateCache = {};
  // Track last known portfolio per symbol to detect close events
  const positionCache = {};

  function isTradeMessage(data) {
    try {
      const msg = typeof data === "string" ? JSON.parse(data) : data;
      return (
        msg &&
        msg.cmd &&
        ["order", "position", "account"].includes(msg.cmd)
      );
    } catch {
      return false;
    }
  }

  function parseAndForward(rawData) {
    try {
      const msg = typeof rawData === "string" ? JSON.parse(rawData) : rawData;
      if (!msg || !msg.cmd) return;

      if (msg.cmd === "order") {
        handleOrderMessage(msg);
      } else if (msg.cmd === "position") {
        handlePositionMessage(msg);
      }
    } catch (e) {
      console.error("[WC-MT5] Error parsing WebSocket message:", e);
    }
  }

  function handleOrderMessage(msg) {
    const data = msg.data;
    if (!data) return;

    // data is keyed by symbol, e.g. {"CM.MNQH6": {order details}}
    for (const [symbol, order] of Object.entries(data)) {
      const orderId = order.order_id;
      const orderState = order.order_state;

      // We care about state transitions:
      // order_state 3 = sent/pending → detect new pending orders (limit/stop)
      // order_state 4 = filled → trade executed
      // order_state 5 = cancelled
      // order_state 6 = rejected

      const cacheKey = `${orderId}_${orderState}`;
      if (orderStateCache[cacheKey]) continue; // already processed
      orderStateCache[cacheKey] = true;

      // Determine order direction from qty_sent
      const qtySent = order.qty_sent || 0;
      const qtyDone = order.qty_done || 0;
      const side = qtySent > 0 ? "BUY" : qtySent < 0 ? "SELL" : "UNKNOWN";
      const quantity = Math.abs(qtySent);

      // Determine order type from order_kind
      // Based on WealthCharts data: 3 = market (observed)
      // We'll map others as we discover them
      let orderType = "MARKET";
      switch (order.order_kind) {
        case 1:
          orderType = "LIMIT";
          break;
        case 2:
          orderType = "STOP";
          break;
        case 3:
          orderType = "MARKET";
          break;
        case 4:
          orderType = "STOP_LIMIT";
          break;
        default:
          orderType = `KIND_${order.order_kind}`;
      }

      const signal = {
        type: "ORDER",
        symbol: symbol,
        order_id: orderId,
        order_state: orderState,
        order_kind: order.order_kind,
        order_type: orderType,
        side: side,
        quantity: quantity,
        qty_sent: qtySent,
        qty_done: qtyDone,
        price_sent: order.price_sent || 0,
        price_done: order.price_done || 0,
        bracket_id: order.bracket_id || null,
        copier_id: order.copier_id || null,
        account_id: order.account_id,
        order_date: order.order_date,
        timestamp: Date.now(),
      };

      console.log("[WC-MT5] Order signal:", signal);
      sendToMiddleware(signal);
      sendToContentScript(signal);
    }
  }

  function handlePositionMessage(msg) {
    const data = msg.data;
    if (!data) return;

    for (const [symbol, pos] of Object.entries(data)) {
      const portfolio = pos.portfolio || 0;
      const prevPortfolio = positionCache[symbol]?.portfolio;

      // Detect position changes
      const isNewPosition =
        (prevPortfolio === 0 || prevPortfolio === undefined) && portfolio !== 0;
      const isClosedPosition =
        prevPortfolio !== 0 && prevPortfolio !== undefined && portfolio === 0;
      const isModifiedPosition =
        prevPortfolio !== undefined &&
        prevPortfolio !== 0 &&
        portfolio !== 0 &&
        prevPortfolio !== portfolio;

      // Update cache
      positionCache[symbol] = {
        portfolio: portfolio,
        avg_price: pos.avg_price,
        pnl: pos.pnl,
        updated_at: pos.updated_at,
      };

      let eventType = null;
      if (isNewPosition) eventType = "POSITION_OPEN";
      else if (isClosedPosition) eventType = "POSITION_CLOSE";
      else if (isModifiedPosition) eventType = "POSITION_UPDATE";
      else continue; // no meaningful change (same portfolio value)

      const signal = {
        type: eventType,
        symbol: symbol,
        portfolio: portfolio,
        side: portfolio > 0 ? "LONG" : portfolio < 0 ? "SHORT" : "FLAT",
        quantity: Math.abs(portfolio),
        avg_price: pos.avg_price || 0,
        pnl: pos.pnl || 0,
        balance: pos.balance || 0,
        commission: pos.comm || 0,
        account_id: pos.account_id,
        account_type: pos.account_type,
        prev_portfolio: prevPortfolio || 0,
        timestamp: Date.now(),
      };

      console.log("[WC-MT5] Position signal:", signal);
      sendToMiddleware(signal);
      sendToContentScript(signal);
    }
  }

  function sendToMiddleware(signal) {
    fetch(`${MIDDLEWARE_URL}/api/signal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(signal),
    }).catch((err) => {
      console.warn("[WC-MT5] Could not reach middleware:", err.message);
    });
  }

  function sendToContentScript(signal) {
    window.postMessage(
      { type: "WC_MT5_TRADE_SIGNAL", payload: signal },
      "*"
    );
  }

  // Monkey-patch WebSocket
  window.WebSocket = function (url, protocols) {
    const ws = protocols
      ? new OriginalWebSocket(url, protocols)
      : new OriginalWebSocket(url);

    const originalAddEventListener = ws.addEventListener.bind(ws);

    // Intercept messages via addEventListener
    ws.addEventListener = function (type, listener, options) {
      if (type === "message") {
        const wrappedListener = function (event) {
          try {
            if (isTradeMessage(event.data)) {
              parseAndForward(event.data);
            }
          } catch (e) {
            // Don't break the original app
          }
          return listener.call(this, event);
        };
        return originalAddEventListener(type, wrappedListener, options);
      }
      return originalAddEventListener(type, listener, options);
    };

    // Also intercept via onmessage setter
    let _onmessage = null;
    Object.defineProperty(ws, "onmessage", {
      get() {
        return _onmessage;
      },
      set(handler) {
        _onmessage = function (event) {
          try {
            if (isTradeMessage(event.data)) {
              parseAndForward(event.data);
            }
          } catch (e) {
            // Don't break the original app
          }
          return handler.call(this, event);
        };
      },
    });

    return ws;
  };

  // Copy static properties
  window.WebSocket.prototype = OriginalWebSocket.prototype;
  window.WebSocket.CONNECTING = OriginalWebSocket.CONNECTING;
  window.WebSocket.OPEN = OriginalWebSocket.OPEN;
  window.WebSocket.CLOSING = OriginalWebSocket.CLOSING;
  window.WebSocket.CLOSED = OriginalWebSocket.CLOSED;

  console.log("[WC-MT5] WebSocket interceptor loaded. Monitoring trade signals...");
})();
