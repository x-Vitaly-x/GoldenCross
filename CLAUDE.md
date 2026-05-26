# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GoldenCross is an algorithmic stock trading bot. It trades ETFs on Trading212 using a rule-based strategy enhanced with AI analysis via Together.ai.

**Goal**: Validate that algorithmic trading can beat a passive VWCE ETF buy-and-hold strategy on a risk-adjusted basis before committing serious capital.

## Current Phase

**Phase 1 — Paper trading (no real money).** The bot runs against the Trading212 demo environment to accumulate real signal/trade history. Phase 2 (live, small account ~100 EUR) begins only after Phase 1 demonstrates consistent positive returns vs. the VWCE benchmark over 4–8 weeks.

## Running the Bot

```bash
python3.12 -m venv .venv        # one-time setup
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in API keys
```

**Dashboard (recommended)** — runs the bot and web panel together:
```bash
python dashboard.py             # serves on http://localhost:8000
# Remote access via Cloudflare Tunnel (free):
cloudflared tunnel --url http://localhost:8000
```

**Standalone bot** (no UI):
```bash
python main.py
```

Run tests:
```bash
pytest tests/ -v
```

## Project Structure

```
main.py         # entry point — hourly loop, orchestrates everything
broker.py       # Trading212 REST API wrapper (demo + live)
data.py         # market data via yfinance (hourly OHLCV)
strategy.py     # signal generation: SMA crossover + RSI filter
ai_analyst.py   # Together.ai LLM analysis of signals
tracker.py      # CSV trade log + JSON state persistence
config.py       # env var loading
logs/           # trades.csv and decisions.csv (gitignored)
state.json      # current position state (gitignored)
```

## Architecture

Each hourly cycle in `main.py:run_once()`:
1. Load state (`tracker.load_state`) — know if we hold a position
2. Fetch 60 days of hourly OHLCV via `data.fetch_ohlcv` (yfinance)
3. Generate signal via `strategy.generate_signal` — BUY / SELL / HOLD
4. Get AI commentary via `ai_analyst.analyse` (Together.ai, non-blocking to trading decision)
5. Execute via `broker` if signal differs from current position
6. Log everything via `tracker` — both the decision and any trade

The AI analysis from Together.ai is **logged for later review** but does not override the rule-based signal. It is there to build a dataset of LLM reasoning quality for future phases.

## Key Configuration (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `T212_API_KEY` | Trading212 API key (Settings → API) | required |
| `T212_MODE` | `demo` or `live` | `demo` |
| `TOGETHER_API_KEY` | Together.ai API key | required |
| `AI_MODEL` | Together.ai model name | `meta-llama/Llama-3.3-70B-Instruct-Turbo` |
| `POSITION_FRACTION` | Fraction of free cash to deploy per trade | `0.95` |
| `STOP_LOSS_PCT` | Sell if position drops this fraction below entry price | `0.10` |

## Broker API Notes

- **Demo URL**: `https://demo.trading212.com/api/v0`
- **Live URL**: `https://live.trading212.com/api/v0`
- Auth header: `Authorization: <API_KEY>` (no "Bearer" prefix)
- Only "Invest and ISA" account types are supported (not CFD)
- Market orders only in the current API version; limit orders are available but not used yet
- Selling requires negative quantity: `{"ticker": "X", "quantity": -1.5}`
- Rate limit on positions endpoint: 1 req/s

## Strategy

**SMA crossover + RSI filter** on hourly candles:
- **BUY**: SMA50 crosses above SMA200 AND RSI < 65
- **SELL**: SMA50 crosses below SMA200 AND RSI > 35
- **STOP_LOSS**: price has fallen ≥ `STOP_LOSS_PCT` below entry (overrides signal, logged as `STOP_LOSS` in decisions.csv)
- **HOLD**: everything else

Single position model: the bot is either 100% in the ETF or 100% cash. No partial positions.

## Tax Context (Germany)

- Abgeltungsteuer: **26.375%** flat on net capital gains
- First **€1,000/year** tax-free (Freistellungsauftrag — must be filed in-app with Trading212)
- Tax is computed on **net annual gains** (broker maintains a Verlustverrechnungstopf)
- Transaction commissions are baked into cost basis; account fees are NOT deductible
- Trading212 is commission-free → no fee drag on small accounts
- For the Phase 1 trial (paper) and Phase 2 (100 EUR), gains will be well within the €1,000 allowance

## Profitability Benchmark

The bot must beat **VWCE buy-and-hold after tax** to justify active management at scale. VWCE (accumulating) pays only Vorabpauschale (~0.2–0.4%/yr) until sale, giving it a compounding tax-deferral advantage. At scale, the bot needs >10% gross annual returns to outperform a passive ETF approach after Abgeltungsteuer.

## What to Measure in Phase 1

`logs/decisions.csv` and `logs/trades.csv` are the primary data source for the Phase 2 go/no-go decision:
- Return vs. VWCE benchmark over the same period
- Win rate on trades
- Max drawdown
- Quality of AI reasoning (subjective review of `ai_reasoning` column)
