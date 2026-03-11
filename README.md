# WealthCharts → MT5 Trade Copier

Real-time trade copier that replicates manual operations from WealthCharts (APEX Futures) to MetaTrader 5.

## Features

- **Real-time WebSocket interception** — captures trades directly from WealthCharts (zero-delay)
- **Symbol Mapping** — map WealthCharts symbols to MT5 symbols (e.g., CM.MNQH6 → NAS100)
- **Lot Multiplier** — adjust position sizes with a configurable multiplier
- **Reverse Mode** — flip BUY↔SELL for inverse copy trading
- **Telegram Notifications** — instant alerts for every copied trade
- **Web Dashboard** — configure everything from a local web interface
- **All order types** — Market, Limit, Stop, Stop-Limit
- **Position sync** — automatic close when WealthCharts position is closed

## Architecture

```
WealthCharts (Browser)
    │ WebSocket messages intercepted
    ▼
Chrome Extension
    │ HTTP POST to localhost
    ▼
Python Middleware (localhost:5000)
    │ Symbol mapping + Lot multiplier + Reverse mode
    ├──▶ MetaTrader 5 (via MT5 Python API)
    └──▶ Telegram Bot (notifications)
```

## Requirements

- **Windows 10/11** (MT5 runs only on Windows)
- **Python 3.10+** ([python.org](https://python.org))
- **Google Chrome** (for the extension)
- **MetaTrader 5** terminal installed and logged in
- **WealthCharts** open in Chrome

## Quick Start

### 1. Install the Chrome Extension

1. Open Chrome → go to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right)
3. Click **"Load unpacked"**
4. Select the `chrome-extension/` folder from this project
5. The extension icon should appear in your toolbar

### 2. Start the Middleware

1. Open the `middleware/` folder
2. Double-click **`start.bat`**
   - First run will create a virtual environment and install dependencies
   - Server starts on `http://127.0.0.1:5000`

### 3. Configure via Dashboard

1. Open `http://127.0.0.1:5000` in your browser
2. **MT5 Connection**: Enter your MT5 login, password, server, and terminal path
3. **Symbol Mapping**: Map your WealthCharts symbols to MT5 symbols
4. **Lot Multiplier**: Set your desired position size multiplier
5. **Reverse Mode**: Toggle if you want to invert trade directions
6. **Telegram**: Enter your bot token and chat ID for notifications

### 4. Start Trading

1. Open WealthCharts in Chrome
2. The extension will automatically detect and intercept trade signals
3. Execute trades on WealthCharts — they'll be copied to MT5 in real-time
4. Check the dashboard for live status and logs

## Symbol Mapping Examples

| WealthCharts | MT5 | Description |
|---|---|---|
| CM.MNQH6 | NAS100 | Micro Nasdaq |
| CM.MESH6 | US500 | Micro S&P 500 |
| CM.MYMH6 | US30 | Micro Dow Jones |

## Telegram Setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the bot token
4. Send a message to your new bot, then visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
5. Find your `chat_id` in the response
6. Enter both in the dashboard

## Troubleshooting

- **Extension shows "OFF"**: Make sure the middleware is running (start.bat)
- **MT5 not connecting**: Verify the terminal path and credentials in the dashboard
- **No signals**: Make sure WealthCharts is open in Chrome (not another browser)
- **Symbols not found**: Check the symbol mapping matches your MT5 broker's symbol names

## Files

```
wc-mt5-copier/
├── chrome-extension/        # Chrome extension (WebSocket interceptor)
│   ├── manifest.json
│   ├── injector.js          # Content script (injects interceptor)
│   ├── interceptor.js       # WebSocket monkey-patch (runs in page)
│   ├── background.js        # Service worker
│   ├── popup.html/js        # Extension popup UI
│   └── icons/
├── middleware/               # Python middleware + MT5 bridge
│   ├── server.py            # Main Flask server
│   ├── mt5_bridge.py        # MetaTrader 5 integration
│   ├── telegram_notifier.py # Telegram bot notifications
│   ├── config.py            # Configuration manager
│   ├── config.json          # Settings (auto-generated)
│   ├── start.bat            # Windows launcher
│   ├── requirements.txt
│   └── templates/
│       └── dashboard.html   # Web dashboard
└── README.md
```

## License

Private — built for client use only.
