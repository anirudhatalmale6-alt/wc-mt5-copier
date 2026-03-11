"""
Telegram Notifier: Sends trade notifications via Telegram bot.
"""

import logging
import threading
import requests

logger = logging.getLogger("wc-mt5.telegram")


class TelegramNotifier:
    def __init__(self, config):
        self.config = config
        self.enabled = False
        self._update()

    def _update(self):
        tg_cfg = self.config.get("telegram", {})
        self.enabled = tg_cfg.get("enabled", False)
        self.bot_token = tg_cfg.get("bot_token", "")
        self.chat_id = tg_cfg.get("chat_id", "")

    def reload(self, config):
        self.config = config
        self._update()

    def send(self, text, parse_mode="HTML"):
        """Send a message via Telegram. Runs in a background thread."""
        if not self.enabled or not self.bot_token or not self.chat_id:
            return

        def _send():
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                resp = requests.post(
                    url,
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                    },
                    timeout=10,
                )
                if resp.status_code != 200:
                    logger.error(f"Telegram API error: {resp.status_code} {resp.text}")
            except Exception as e:
                logger.error(f"Telegram send failed: {e}")

        threading.Thread(target=_send, daemon=True).start()

    def notify_order(self, signal, mt5_result, mapped_symbol):
        """Send a formatted notification for an executed order."""
        side = signal.get("side", "?")
        qty = signal.get("quantity", 0)
        wc_symbol = signal.get("symbol", "?")
        price = signal.get("price_done", 0) or signal.get("price_sent", 0)

        icon = "🟢" if side == "BUY" else "🔴"
        reverse_tag = " (REVERSED)" if self.config.get("reverse_mode") else ""

        mt5_price = mt5_result.get("price", 0) if mt5_result else "N/A"
        mt5_volume = mt5_result.get("volume", 0) if mt5_result else "N/A"
        mt5_status = "✅ Executed" if mt5_result and mt5_result.get("success") else "❌ Failed"
        mt5_error = f"\n<b>Error:</b> {mt5_result.get('error', '')}" if mt5_result and not mt5_result.get("success") else ""

        msg = (
            f"{icon} <b>Trade Copied{reverse_tag}</b>\n"
            f"\n"
            f"<b>WealthCharts:</b>\n"
            f"  Symbol: {wc_symbol}\n"
            f"  Side: {side}\n"
            f"  Qty: {qty}\n"
            f"  Price: {price}\n"
            f"\n"
            f"<b>MT5 ({mapped_symbol}):</b>\n"
            f"  Status: {mt5_status}\n"
            f"  Volume: {mt5_volume}\n"
            f"  Price: {mt5_price}{mt5_error}"
        )
        self.send(msg)

    def notify_close(self, signal, mt5_result, mapped_symbol):
        """Send a notification for a closed position."""
        wc_symbol = signal.get("symbol", "?")
        pnl = signal.get("pnl", 0)
        pnl_icon = "💰" if pnl >= 0 else "💸"

        mt5_status = "✅ Closed" if mt5_result and mt5_result.get("success") else "❌ Close Failed"

        msg = (
            f"🟡 <b>Position Closed</b>\n"
            f"\n"
            f"<b>WealthCharts:</b>\n"
            f"  Symbol: {wc_symbol}\n"
            f"  P&L: {pnl_icon} {pnl}\n"
            f"\n"
            f"<b>MT5 ({mapped_symbol}):</b>\n"
            f"  Status: {mt5_status}"
        )
        self.send(msg)

    def test_message(self):
        """Send a test message to verify configuration."""
        self.send("🔔 <b>WC→MT5 Copier</b>\n\nTest notification — tutto funziona!")
