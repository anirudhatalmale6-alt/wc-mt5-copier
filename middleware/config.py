"""
Configuration manager for the WC→MT5 Trade Copier.
Loads settings from config.json and provides runtime access.
"""

import json
import os
import threading

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULT_CONFIG = {
    "mt5": {
        "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
        "login": 0,
        "password": "",
        "server": "",
    },
    "symbol_mapping": {
        "CM.MNQH6": "NAS100",
        "CM.MESH6": "US500",
        "CM.MYML6": "US30",
    },
    "lot_multiplier": 1.0,
    "reverse_mode": False,
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
    },
    "filters": {
        "account_ids": [],
        "symbols": [],
        "min_order_state": 4,
    },
    "general": {
        "auto_start_mt5": True,
        "log_level": "INFO",
        "max_log_entries": 500,
    },
}

_config = None
_lock = threading.Lock()


def load_config():
    """Load configuration from config.json, creating it with defaults if missing."""
    global _config
    with _lock:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            # Merge with defaults so new keys are always present
            _config = _deep_merge(DEFAULT_CONFIG, saved)
        else:
            _config = DEFAULT_CONFIG.copy()
            save_config()
        return _config


def get_config():
    """Return the current configuration (loads if not yet loaded)."""
    global _config
    if _config is None:
        return load_config()
    return _config


def save_config(new_config=None):
    """Save configuration to config.json."""
    global _config
    with _lock:
        if new_config is not None:
            _config = new_config
        with open(CONFIG_FILE, "w") as f:
            json.dump(_config, f, indent=2)
    return _config


def update_config(partial):
    """Partially update configuration and save."""
    global _config
    cfg = get_config()
    updated = _deep_merge(cfg, partial)
    return save_config(updated)


def _deep_merge(base, override):
    """Deep-merge two dicts; override values take precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
