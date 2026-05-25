# GoldenCross

An algorithmic ETF trading bot for [Trading212](https://www.trading212.com/) with an AI commentary layer via [Together.ai](https://www.together.ai/).

The strategy is a simple SMA crossover + RSI filter on hourly candles. The bot is either fully in or fully out of a single ETF position — no partial sizing. The AI analysis (LLaMA via Together.ai) is logged alongside each decision for later review but does **not** influence trade execution.

> **Disclaimer**: This project is for educational and experimental purposes only. It is not financial advice. Algorithmic trading involves significant risk of loss. Use at your own risk.

---

## Features

- Hourly trading loop with SMA20/SMA50 crossover + RSI filter
- Executes market orders via Trading212 REST API (demo and live modes)
- AI commentary on each signal via Together.ai (non-blocking, logged only)
- Web dashboard with live P&L, trade history, and bot controls
- CSV trade log and JSON state persistence
- Supports multiple instruments

## Strategy

**BUY**: SMA20 crosses above SMA50 AND RSI(14) < 65  
**SELL**: SMA20 crosses below SMA50 AND RSI(14) > 35  
**HOLD**: everything else

Single position model: the bot is either 100% deployed in the ETF or 100% cash.

## Requirements

- Python 3.12+
- Trading212 account (demo or live; Invest/ISA account type — not CFD)
- [Together.ai](https://api.together.ai/) API key

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and fill in your API keys
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `T212_API_KEY` | Trading212 API key (Settings → API) | required |
| `T212_MODE` | `demo` or `live` | `demo` |
| `TOGETHER_API_KEY` | Together.ai API key | required |
| `AI_MODEL` | Together.ai model name | `meta-llama/Llama-3.3-70B-Instruct-Turbo` |
| `TICKER_T212` | Trading212 instrument ticker (e.g. `VWCEd_EQ`) | `VWCEd_EQ` |
| `TICKER_YFINANCE` | yfinance ticker for the same instrument (e.g. `VWCE.DE`) | `VWCE.DE` |
| `POSITION_FRACTION` | Fraction of free cash to deploy per BUY signal | `0.95` |
| `DASHBOARD_TOKEN` | Secret token for dashboard authentication | required |

## Running

**Dashboard** (bot + web UI on http://localhost:8000):
```bash
python dashboard.py
```

Remote access via Cloudflare Tunnel (free, no port-forwarding needed):
```bash
cloudflared tunnel --url http://localhost:8000
```

**Bot only** (no UI):
```bash
python main.py
```

**Tests**:
```bash
pytest tests/ -v
```

## Project Structure

```
main.py         # entry point — hourly loop
broker.py       # Trading212 REST API wrapper
data.py         # market data via yfinance (hourly OHLCV)
strategy.py     # signal generation: SMA crossover + RSI filter
ai_analyst.py   # Together.ai LLM signal commentary
tracker.py      # CSV trade log + JSON state persistence
instruments.py  # multi-instrument management
config.py       # env var loading
dashboard.py    # FastAPI web dashboard
templates/      # dashboard HTML
logs/           # trades.csv and decisions.csv (gitignored)
state.json      # current position state (gitignored)
```

## Logs

`logs/decisions.csv` — every hourly decision with price, indicators, and AI reasoning.  
`logs/trades.csv` — every executed trade with quantity, price, and EUR value.

Both are gitignored and contain no data in the repository.

## License

[MIT](LICENSE)
