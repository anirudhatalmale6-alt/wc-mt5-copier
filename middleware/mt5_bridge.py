"""
MT5 Bridge: Handles all interaction with MetaTrader 5 terminal.
Uses the official MetaTrader5 Python library.
LAZY IMPORT: MetaTrader5 is imported only when connect() is called,
to prevent hanging during module import.
"""

import logging
import time
from datetime import datetime

logger = logging.getLogger("wc-mt5.bridge")

# MetaTrader5 module reference (loaded lazily)
mt5 = None
MT5_AVAILABLE = None  # None = not yet checked


def _load_mt5():
    """Lazy-load the MetaTrader5 module."""
    global mt5, MT5_AVAILABLE
    if MT5_AVAILABLE is not None:
        return MT5_AVAILABLE
    try:
        import MetaTrader5 as _mt5
        mt5 = _mt5
        MT5_AVAILABLE = True
        logger.info("MetaTrader5 library loaded successfully")
    except ImportError:
        MT5_AVAILABLE = False
        logger.warning("MetaTrader5 library not available. Running in simulation mode.")
    return MT5_AVAILABLE


class MT5Bridge:
    def __init__(self, config):
        self.config = config
        self.connected = False
        self.simulation_mode = True  # Start in simulation mode until MT5 is loaded

    def connect(self):
        """Initialize and connect to MT5 terminal."""
        # Try to load MT5 library
        if not _load_mt5():
            logger.info("[SIM] MT5 not available — simulation mode active")
            self.simulation_mode = True
            self.connected = True
            return True

        self.simulation_mode = False
        mt5_cfg = self.config.get("mt5", {})

        # Initialize MT5
        init_kwargs = {}
        if mt5_cfg.get("path"):
            init_kwargs["path"] = mt5_cfg["path"]
        if mt5_cfg.get("login"):
            init_kwargs["login"] = int(mt5_cfg["login"])
        if mt5_cfg.get("password"):
            init_kwargs["password"] = mt5_cfg["password"]
        if mt5_cfg.get("server"):
            init_kwargs["server"] = mt5_cfg["server"]

        if not mt5.initialize(**init_kwargs):
            error = mt5.last_error()
            logger.error(f"MT5 initialization failed: {error}")
            self.connected = False
            return False

        info = mt5.account_info()
        if info:
            logger.info(
                f"MT5 connected: Account #{info.login} | Balance: {info.balance} | Server: {info.server}"
            )
        self.connected = True
        return True

    def disconnect(self):
        """Shutdown MT5 connection."""
        if not self.simulation_mode and mt5:
            mt5.shutdown()
        self.connected = False
        logger.info("MT5 disconnected")

    def is_connected(self):
        """Check if MT5 is connected."""
        if self.simulation_mode:
            return self.connected
        if not mt5:
            return False
        info = mt5.terminal_info()
        return info is not None and info.connected

    def get_account_info(self):
        """Get MT5 account info."""
        if self.simulation_mode:
            return {
                "login": 0,
                "balance": 100000,
                "equity": 100000,
                "server": "SimulationServer",
                "name": "Simulation Account",
            }
        if not mt5:
            return None
        info = mt5.account_info()
        if info:
            return {
                "login": info.login,
                "balance": info.balance,
                "equity": info.equity,
                "server": info.server,
                "name": info.name,
            }
        return None

    def place_order(self, symbol, side, volume, order_type="MARKET", price=0, sl=0, tp=0, comment=""):
        """Place an order on MT5."""
        if self.simulation_mode:
            result = {
                "success": True,
                "order_id": int(time.time() * 1000),
                "symbol": symbol,
                "side": side,
                "volume": volume,
                "price": price or 99999.99,
                "comment": comment,
                "simulation": True,
            }
            logger.info(f"[SIM] Order placed: {side} {volume} {symbol} @ {result['price']}")
            return result

        if not mt5 or not self.connected:
            logger.error("MT5 not connected, cannot place order")
            return None

        # Get symbol info
        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            logger.error(f"Symbol {symbol} not found in MT5")
            return None
        if not sym_info.visible:
            mt5.symbol_select(symbol, True)

        # Build order request
        request = {
            "symbol": symbol,
            "volume": float(volume),
            "comment": comment or "WC-MT5 Copier",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if order_type == "MARKET":
            request["action"] = mt5.TRADE_ACTION_DEAL
            if side == "BUY":
                request["type"] = mt5.ORDER_TYPE_BUY
                request["price"] = mt5.symbol_info_tick(symbol).ask
            else:
                request["type"] = mt5.ORDER_TYPE_SELL
                request["price"] = mt5.symbol_info_tick(symbol).bid
        elif order_type == "LIMIT":
            request["action"] = mt5.TRADE_ACTION_PENDING
            request["price"] = price
            request["type"] = (
                mt5.ORDER_TYPE_BUY_LIMIT if side == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
            )
        elif order_type == "STOP":
            request["action"] = mt5.TRADE_ACTION_PENDING
            request["price"] = price
            request["type"] = (
                mt5.ORDER_TYPE_BUY_STOP if side == "BUY" else mt5.ORDER_TYPE_SELL_STOP
            )
        elif order_type == "STOP_LIMIT":
            request["action"] = mt5.TRADE_ACTION_PENDING
            request["price"] = price
            request["type"] = (
                mt5.ORDER_TYPE_BUY_STOP_LIMIT
                if side == "BUY"
                else mt5.ORDER_TYPE_SELL_STOP_LIMIT
            )

        if sl > 0:
            request["sl"] = sl
        if tp > 0:
            request["tp"] = tp

        result = mt5.order_send(request)
        if result is None:
            error = mt5.last_error()
            logger.error(f"Order send failed: {error}")
            return None

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(
                f"Order executed: {side} {volume} {symbol} @ {result.price} | Ticket #{result.order}"
            )
            return {
                "success": True,
                "order_id": result.order,
                "symbol": symbol,
                "side": side,
                "volume": volume,
                "price": result.price,
                "comment": result.comment,
            }
        else:
            logger.error(
                f"Order failed: retcode={result.retcode} comment={result.comment}"
            )
            return {
                "success": False,
                "retcode": result.retcode,
                "error": result.comment,
            }

    def close_position(self, symbol, comment=""):
        """Close all positions for a given symbol."""
        if self.simulation_mode:
            logger.info(f"[SIM] Closed all positions for {symbol}")
            return {"success": True, "symbol": symbol, "simulation": True}

        if not mt5 or not self.connected:
            logger.error("MT5 not connected")
            return None

        positions = mt5.positions_get(symbol=symbol)
        if positions is None or len(positions) == 0:
            logger.info(f"No open positions for {symbol}")
            return {"success": True, "symbol": symbol, "message": "No positions to close"}

        results = []
        for pos in positions:
            close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
            price = (
                mt5.symbol_info_tick(symbol).bid
                if pos.type == 0
                else mt5.symbol_info_tick(symbol).ask
            )

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": pos.volume,
                "type": close_type,
                "position": pos.ticket,
                "price": price,
                "comment": comment or "WC-MT5 Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Position closed: Ticket #{pos.ticket} | {symbol}")
                results.append({"success": True, "ticket": pos.ticket})
            else:
                err = result.comment if result else "Unknown error"
                logger.error(f"Failed to close position #{pos.ticket}: {err}")
                results.append({"success": False, "ticket": pos.ticket, "error": err})

        return {"success": all(r["success"] for r in results), "results": results}

    def get_positions(self):
        """Get all open positions."""
        if self.simulation_mode:
            return []
        if not mt5:
            return []
        positions = mt5.positions_get()
        if positions is None:
            return []
        return [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == 0 else "SELL",
                "volume": p.volume,
                "price_open": p.price_open,
                "price_current": p.price_current,
                "profit": p.profit,
                "sl": p.sl,
                "tp": p.tp,
                "comment": p.comment,
            }
            for p in positions
        ]
