"""
GoldenCross dashboard — FastAPI web panel + bot lifecycle manager.

Run with:
    python dashboard.py

Then expose remotely:
    cloudflared tunnel --url http://localhost:8000
"""
from __future__ import annotations

import asyncio
import collections
import csv
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse

import ai_analyst
import broker
import config
import data as data_module
import instruments as instr_module
import main as bot
import tracker

# ── Logging → WebSocket bridge ───────────────────────────────────────────────

_ws_clients: set[WebSocket] = set()
_log_queue: asyncio.Queue[str] = asyncio.Queue()
_log_history: collections.deque[str] = collections.deque(maxlen=200)


class _WsLogHandler(logging.Handler):
    """Pushes log records into the asyncio queue from any thread."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        _log_history.append(msg)
        try:
            self._loop.call_soon_threadsafe(_log_queue.put_nowait, msg)
        except RuntimeError:
            pass


async def _broadcast_logs() -> None:
    while True:
        msg = await _log_queue.get()
        dead: set[WebSocket] = set()
        for ws in list(_ws_clients):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        _ws_clients.difference_update(dead)


# ── Bot lifecycle ─────────────────────────────────────────────────────────────

_bot_task: asyncio.Task | None = None
_stop_event: asyncio.Event = asyncio.Event()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bot")
_api_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="api")
log = logging.getLogger("dashboard")


async def _bot_loop() -> None:
    _stop_event.clear()
    log.info("Bot started via dashboard")
    while True:
        try:
            if bot._is_market_open():
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(_executor, bot.run_once)
            else:
                log.info("Market closed, skipping")
        except Exception as e:
            log.error(f"Bot cycle error: {e}", exc_info=True)

        now = datetime.now(timezone.utc)
        wait = (59 - now.minute) * 60 + (60 - now.second)
        log.info(f"Next run in {wait:.0f}s ({wait / 60:.1f} min)")

        # Sleep until next hour, but wake immediately if stop is requested
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=float(wait))
            break  # stop was requested
        except asyncio.TimeoutError:
            pass  # normal — time for the next cycle

    log.info("Bot stopped")


# ── App lifespan ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    if len(config.DASHBOARD_TOKEN) < 20:
        raise RuntimeError(
            "DASHBOARD_TOKEN is missing or too short — generate one with: openssl rand -hex 24"
        )

    loop = asyncio.get_event_loop()
    handler = _WsLogHandler(loop)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"
    ))
    logging.getLogger().addHandler(handler)
    asyncio.create_task(_broadcast_logs())

    yield

    global _bot_task
    if _bot_task and not _bot_task.done():
        _stop_event.set()
        await asyncio.wait_for(_bot_task, timeout=5)
    _executor.shutdown(wait=False)
    _api_executor.shutdown(wait=False)


app = FastAPI(lifespan=lifespan)


# ── Auth ──────────────────────────────────────────────────────────────────────

def _check_token(gc_session: str = Cookie(default="")) -> None:
    if gc_session != config.DASHBOARD_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.post("/api/login")
async def api_login(body: dict, response: Response) -> dict[str, str]:
    if body.get("token") != config.DASHBOARD_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    response.set_cookie("gc_session", config.DASHBOARD_TOKEN, httponly=True, samesite="strict")
    return {"status": "ok"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index():
    return Path("templates/index.html").read_text()


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/api/status", dependencies=[Depends(_check_token)])
async def api_status() -> dict[str, Any]:
    global _bot_task
    running = _bot_task is not None and not _bot_task.done()

    loop = asyncio.get_event_loop()

    try:
        account = await loop.run_in_executor(_api_executor, broker.get_account)
        cash = account.get("cash", {}).get("availableToTrade", 0)
        total = account.get("totalValue", 0)
    except Exception:
        cash = total = None

    state = tracker.load_state()
    positions_data = []
    for ticker, pos in state.get("positions", {}).items():
        try:
            live = await loop.run_in_executor(
                _api_executor, lambda t=ticker: broker.get_position(t)
            )
            current_price = float(live["currentPrice"]) if live else float(pos["entry_price"])
            pnl = (current_price - float(pos["entry_price"])) * float(pos["quantity"])
            pnl_pct = pnl / (float(pos["entry_price"]) * float(pos["quantity"])) * 100
            positions_data.append({
                "ticker": pos["ticker"],
                "quantity": pos["quantity"],
                "entry_price": pos["entry_price"],
                "current_price": current_price,
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            })
        except Exception:
            positions_data.append(pos)

    last_decision = None
    try:
        with open(tracker.DECISIONS_FILE, newline="") as f:
            rows = list(csv.DictReader(f))
            if rows:
                last_decision = rows[-1]
    except FileNotFoundError:
        pass

    return {
        "bot_running": running,
        "market_open": bot._is_market_open(),
        "account": {"cash": cash, "total": total},
        "positions": positions_data,
        "last_decision": last_decision,
    }


@app.get("/api/decisions", dependencies=[Depends(_check_token)])
async def api_decisions() -> list[dict]:
    try:
        with open(tracker.DECISIONS_FILE, newline="") as f:
            return list(csv.DictReader(f))[-20:][::-1]
    except FileNotFoundError:
        return []


@app.get("/api/trades", dependencies=[Depends(_check_token)])
async def api_trades() -> list[dict]:
    try:
        with open(tracker.TRADES_FILE, newline="") as f:
            return list(csv.DictReader(f))[::-1]
    except FileNotFoundError:
        return []


@app.post("/api/bot/start", dependencies=[Depends(_check_token)])
async def api_bot_start() -> dict[str, str]:
    global _bot_task
    if _bot_task and not _bot_task.done():
        return {"status": "already_running"}
    _bot_task = asyncio.create_task(_bot_loop())
    return {"status": "started"}


@app.post("/api/bot/stop", dependencies=[Depends(_check_token)])
async def api_bot_stop() -> dict[str, str]:
    global _bot_task
    if _bot_task and not _bot_task.done():
        _stop_event.set()
        return {"status": "stopping"}
    return {"status": "not_running"}


# ── Instrument management ─────────────────────────────────────────────────────

@app.get("/api/instruments/name", dependencies=[Depends(_check_token)])
async def api_instrument_name(ticker_yf: str = Query(default="")) -> dict[str, str]:
    if not ticker_yf.strip():
        raise HTTPException(status_code=422, detail="ticker_yf is required")
    loop = asyncio.get_event_loop()
    name = await loop.run_in_executor(_api_executor, lambda: data_module.get_instrument_name(ticker_yf))
    return {"name": name}


@app.get("/api/instruments", dependencies=[Depends(_check_token)])
async def api_instruments() -> list[dict]:
    return instr_module.load_instruments()


@app.post("/api/instruments", dependencies=[Depends(_check_token)])
async def api_add_instrument(body: dict) -> dict:
    t212 = body.get("ticker_t212", "").strip()
    yf = body.get("ticker_yfinance", "").strip()
    name = body.get("name", t212).strip()
    if not t212 or not yf:
        raise HTTPException(status_code=422, detail="ticker_t212 and ticker_yfinance are required")
    try:
        return instr_module.add_instrument(t212, yf, name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.delete("/api/instruments/{ticker}", dependencies=[Depends(_check_token)])
async def api_remove_instrument(ticker: str) -> dict[str, str]:
    instr_module.remove_instrument(ticker)
    return {"status": "removed"}


@app.patch("/api/instruments/{ticker}", dependencies=[Depends(_check_token)])
async def api_toggle_instrument(ticker: str, body: dict) -> dict[str, str]:
    enabled = bool(body.get("enabled", True))
    instr_module.toggle_instrument(ticker, enabled)
    return {"status": "updated"}


@app.post("/api/instruments/analyse", dependencies=[Depends(_check_token)])
async def api_analyse_instrument(body: dict) -> dict[str, str]:
    t212 = body.get("ticker_t212", "").strip()
    name = body.get("name", t212).strip()
    if not t212:
        raise HTTPException(status_code=422, detail="ticker_t212 is required")
    existing = instr_module.load_instruments()
    loop = asyncio.get_event_loop()
    analysis = await loop.run_in_executor(
        _api_executor,
        lambda: ai_analyst.analyse_instrument(t212, name, existing),
    )
    return {"analysis": analysis}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    if ws.cookies.get("gc_session") != config.DASHBOARD_TOKEN:
        await ws.close(code=4001)
        return
    await ws.accept()
    for line in _log_history:
        await ws.send_text(line)
    _ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(ws)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)
