"""
WC→MT5 Trade Copier — Main Server
Receives trade signals from the Chrome Extension,
applies transformations, and executes on MT5.
"""

import logging
import os
import sys
import time
from collections import deque
from datetime import datetime

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from config import get_config, load_config, update_config
from mt5_bridge import MT5Bridge
from telegram_notifier import TelegramNotifier

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("copier.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("wc-mt5")

# ---------------------------------------------------------------------------
# App init
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

config = load_config()
bridge = MT5Bridge(config)
notifier = TelegramNotifier(config)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
signal_log = deque(maxlen=config.get("general", {}).get("max_log_entries", 500))
stats = {
    "signals_received": 0,
    "orders_executed": 0,
    "orders_failed": 0,
    "positions_closed": 0,
    "started_at": datetime.now().isoformat(),
}

# Track processed order IDs to avoid duplicates
processed_orders = set()

# Track WealthCharts positions to distinguish open vs close orders
wc_positions = {}  # symbol -> portfolio (qty, sign indicates direction)

# ---------------------------------------------------------------------------
# Signal processing
# ---------------------------------------------------------------------------

def process_signal(signal):
    """Core signal processing pipeline."""
    sig_type = signal.get("type")
    wc_symbol = signal.get("symbol", "")

    stats["signals_received"] += 1

    # Log the signal
    signal["processed_at"] = datetime.now().isoformat()
    signal_log.appendleft(signal)

    logger.info(f"Signal received: {sig_type} | {wc_symbol} | side={signal.get('side')} qty={signal.get('quantity')}")

    cfg = get_config()

    # --- Filters ---
    allowed_accounts = cfg.get("filters", {}).get("account_ids", [])
    if allowed_accounts and signal.get("account_id") not in allowed_accounts:
        logger.info(f"Signal filtered: account_id {signal.get('account_id')} not in allowed list")
        return

    allowed_symbols = cfg.get("filters", {}).get("symbols", [])
    if allowed_symbols and wc_symbol not in allowed_symbols:
        logger.info(f"Signal filtered: symbol {wc_symbol} not in allowed list")
        return

    # --- Symbol mapping ---
    symbol_map = cfg.get("symbol_mapping", {})
    mt5_symbol = symbol_map.get(wc_symbol, wc_symbol)

    # --- Track WealthCharts positions ---
    if sig_type in ("POSITION_OPEN", "POSITION_CLOSE", "POSITION_UPDATE"):
        wc_positions[wc_symbol] = signal.get("portfolio", 0)

    # --- Handle different signal types ---
    if sig_type == "ORDER":
        handle_order(signal, cfg, mt5_symbol, wc_symbol)
    elif sig_type == "POSITION_CLOSE":
        handle_close(signal, cfg, mt5_symbol)
    elif sig_type == "POSITION_OPEN":
        logger.info(f"Position opened: {wc_symbol} portfolio={signal.get('portfolio')}")
    elif sig_type == "POSITION_UPDATE":
        logger.info(f"Position updated: {wc_symbol} portfolio={signal.get('portfolio')}")


def handle_order(signal, cfg, mt5_symbol, wc_symbol):
    """Handle an ORDER signal — execute trade on MT5."""
    order_id = signal.get("order_id")
    order_state = signal.get("order_state")

    # Only process filled orders (state 4) or new pending orders (state 3 for limit/stop)
    order_type = signal.get("order_type", "MARKET")

    # For market orders, wait for fill (state 4)
    # For pending orders (limit/stop), send on state 3
    if order_type == "MARKET" and order_state < 4:
        return
    if order_type in ("LIMIT", "STOP", "STOP_LIMIT") and order_state < 3:
        return

    # Deduplicate
    dedup_key = f"{order_id}_{order_state}"
    if dedup_key in processed_orders:
        return
    processed_orders.add(dedup_key)

    # Limit dedup cache size
    if len(processed_orders) > 10000:
        processed_orders.clear()

    # --- Detect if this is a CLOSE order (not a new open) ---
    # When closing a SHORT (-40), WC sends a BUY order (qty_sent: +40)
    # When closing a LONG (+40), WC sends a SELL order (qty_sent: -40)
    # We detect this by checking if the order opposes the current position
    qty_sent = signal.get("qty_sent", 0)
    current_pos = wc_positions.get(wc_symbol, 0)

    if current_pos != 0:
        # Position exists — check if this order is closing/reducing it
        order_opposes_position = (current_pos > 0 and qty_sent < 0) or (current_pos < 0 and qty_sent > 0)
        if order_opposes_position:
            logger.info(
                f"Order {order_id} is a CLOSE/REDUCE order "
                f"(position={current_pos}, qty_sent={qty_sent}). "
                f"Skipping — POSITION_CLOSE signal will handle MT5 close."
            )
            return

    # --- Lot multiplier ---
    lot_multiplier = cfg.get("lot_multiplier", 1.0)
    quantity = signal.get("quantity", 0)
    mt5_volume = round(quantity * lot_multiplier, 2)

    if mt5_volume <= 0:
        logger.warning(f"Calculated volume is 0 after multiplier, skipping")
        return

    # --- Reverse mode ---
    side = signal.get("side", "BUY")
    if cfg.get("reverse_mode", False):
        side = "SELL" if side == "BUY" else "BUY"
        logger.info(f"Reverse mode: flipped to {side}")

    # --- Price for pending orders ---
    price = signal.get("price_sent", 0) or signal.get("price_done", 0)

    # --- Execute on MT5 ---
    logger.info(f"Executing on MT5: {side} {mt5_volume} {mt5_symbol} ({order_type}) price={price}")

    result = bridge.place_order(
        symbol=mt5_symbol,
        side=side,
        volume=mt5_volume,
        order_type=order_type,
        price=price,
        comment=f"WC|{signal.get('order_id', '')[:8]}",
    )

    if result and result.get("success"):
        stats["orders_executed"] += 1
        logger.info(f"MT5 order executed successfully: {result}")
    else:
        stats["orders_failed"] += 1
        logger.error(f"MT5 order failed: {result}")

    # Telegram notification
    notifier.notify_order(signal, result, mt5_symbol)


def handle_close(signal, cfg, mt5_symbol):
    """Handle a POSITION_CLOSE signal — close positions on MT5."""
    logger.info(f"Closing positions for {mt5_symbol}")

    result = bridge.close_position(mt5_symbol, comment="WC-MT5 Close")

    if result and result.get("success"):
        stats["positions_closed"] += 1
        logger.info(f"MT5 positions closed for {mt5_symbol}")
    else:
        logger.error(f"Failed to close MT5 positions for {mt5_symbol}: {result}")

    notifier.notify_close(signal, result, mt5_symbol)


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    """Serve the web dashboard."""
    return render_template("dashboard.html")


@app.route("/api/health")
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "mt5_connected": bridge.is_connected(),
        "stats": stats,
        "uptime_since": stats["started_at"],
    })


@app.route("/api/signal", methods=["POST"])
def receive_signal():
    """Receive a trade signal from the Chrome Extension."""
    signal = request.get_json()
    if not signal:
        return jsonify({"error": "No data"}), 400

    try:
        process_signal(signal)
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.exception(f"Error processing signal: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/log")
def get_log():
    """Return recent signal log entries."""
    limit = request.args.get("limit", 50, type=int)
    entries = list(signal_log)[:limit]
    return jsonify({"entries": entries})


@app.route("/api/config", methods=["GET"])
def get_configuration():
    """Get current configuration."""
    cfg = get_config()
    # Mask sensitive fields
    safe = dict(cfg)
    if "mt5" in safe:
        mt5_safe = dict(safe["mt5"])
        if mt5_safe.get("password"):
            mt5_safe["password"] = "***"
        safe["mt5"] = mt5_safe
    if "telegram" in safe:
        tg_safe = dict(safe["telegram"])
        if tg_safe.get("bot_token"):
            tg_safe["bot_token"] = tg_safe["bot_token"][:10] + "***"
        safe["telegram"] = tg_safe
    return jsonify(safe)


@app.route("/api/config", methods=["POST"])
def update_configuration():
    """Update configuration."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    cfg = update_config(data)

    # Reload components
    notifier.reload(cfg)

    # If MT5 config changed, reconnect
    if "mt5" in data:
        bridge.config = cfg
        bridge.connect()

    return jsonify({"status": "ok", "config": cfg})


@app.route("/api/mt5/status")
def mt5_status():
    """Get MT5 connection status and account info."""
    return jsonify({
        "connected": bridge.is_connected(),
        "account": bridge.get_account_info(),
        "positions": bridge.get_positions(),
    })


@app.route("/api/mt5/connect", methods=["POST"])
def mt5_connect():
    """Connect/reconnect to MT5."""
    bridge.config = get_config()
    success = bridge.connect()
    return jsonify({"connected": success})


@app.route("/api/telegram/test", methods=["POST"])
def telegram_test():
    """Send a test Telegram notification."""
    notifier.reload(get_config())
    notifier.test_message()
    return jsonify({"status": "ok"})


@app.route("/api/stats")
def get_stats():
    """Get copier statistics."""
    return jsonify(stats)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 60)
    logger.info("  WealthCharts → MT5 Trade Copier")
    logger.info("=" * 60)

    # Connect to MT5 in background thread (don't block server startup)
    if config.get("general", {}).get("auto_start_mt5", True):
        import threading
        def _connect_mt5():
            try:
                bridge.connect()
            except Exception as e:
                logger.error(f"MT5 background connect failed: {e}")
        threading.Thread(target=_connect_mt5, daemon=True).start()
        logger.info("MT5 connection starting in background...")

    # Start server
    logger.info("Starting middleware server on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
