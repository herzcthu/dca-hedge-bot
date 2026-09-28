#!/usr/bin/env python3
"""
BTC-ETH pair scalp helper for Binance USD-M futures.

RETIRED: one-year fee-inclusive backtesting rejected this gap-reversion scalp.
It is preserved for research/reference only and refuses to run unless
ALLOW_RETIRED_GAP_FADING=true is set explicitly.

Default is DRY RUN (no orders). Set DRY_RUN = False only after testnet.

Rules baked in (your plan):
  Notional each leg = available margin * MARGIN_FRACTION_PER_LEG * LEVERAGE (live),
    or NOTIONAL (dry run)
  Enter when |ETH% - BTC%| over WINDOW_SEC >= GAP_ENTER
  TP when estimated net PnL (after fees) >= trade_notional * TP_PNL_FRACTION
  SL when estimated net PnL (after fees) <= -trade_notional * SL_PNL_FRACTION
  Time stop TIME_STOP_SEC
  Flatten if second leg not filled in FILL_WAIT_SEC seconds
"""

from __future__ import annotations

import os
import csv
import json
import time
import base64
import threading
import urllib.parse
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone
from collections import deque, OrderedDict

if __name__ == "__main__" and os.getenv("ALLOW_RETIRED_GAP_FADING", "false").lower() not in ("1", "true", "yes"):
    raise RuntimeError("retired gap-fading strategy is disabled after failed fee-inclusive backtests")

import requests
from cryptography.hazmat.primitives.serialization import load_pem_private_key

try:
    import websocket  # websocket-client package
except ImportError:
    websocket = None

# --- config (override via environment variables) ---
DRY_RUN = os.getenv("DRY_RUN", "true").lower() not in ("0", "false", "no")
BASE = os.getenv("BASE_URL", "https://testnet.binancefuture.com")  # live: https://fapi.binance.com
API_KEY = os.getenv("BINANCE_API_KEY", "")
ED25519_KEY_PATH = os.getenv("BINANCE_ED25519_PRIVATE_KEY_PATH", "")
_ed25519_key = None

NOTIONAL = float(os.getenv("NOTIONAL", "800.0"))
GAP_ENTER = float(os.getenv("GAP_ENTER", "0.0040"))  # 0.40%
GAP_TP = float(os.getenv("GAP_TP", "0.0025"))  # 0.25% snap back
GAP_SL = float(os.getenv("GAP_SL", "0.0042"))  # 0.42% further against
WINDOW_SEC = int(os.getenv("WINDOW_SEC", str(15 * 60)))
FILL_WAIT_SEC = int(os.getenv("FILL_WAIT_SEC", "15"))
TIME_STOP_SEC = int(os.getenv("TIME_STOP_SEC", str(25 * 60)))
MAX_HOLD_SEC = int(os.getenv("MAX_HOLD_SEC", str(TIME_STOP_SEC * 2)))
POLL_SEC = int(os.getenv("POLL_SEC", "2"))
LEVERAGE = int(os.getenv("LEVERAGE", "10"))
ENTRY_ORDER_TYPE = os.getenv("ENTRY_ORDER_TYPE", "LIMIT").upper()
ENTRY_COOLDOWN_SEC = int(os.getenv("ENTRY_COOLDOWN_SEC", "30"))
FEE_RATE = float(os.getenv("FEE_RATE", "0.0004"))
MARGIN_FRACTION_PER_LEG = float(os.getenv("MARGIN_FRACTION_PER_LEG", "0.40"))
DAY_STOP_USD = float(os.getenv("DAY_STOP_USD", "-12.0"))
TP_PNL_FRACTION = float(os.getenv("TP_PNL_FRACTION", "0.0020"))
SL_PNL_FRACTION = float(os.getenv("SL_PNL_FRACTION", "0.0042"))
DAY_STOP_EQUITY_FRACTION = float(os.getenv("DAY_STOP_EQUITY_FRACTION", "0.06"))
MAX_POLL_MOVE_PCT = float(os.getenv("MAX_POLL_MOVE_PCT", "0.0010"))
SHARP_MOVE_WINDOW_SEC = float(os.getenv("SHARP_MOVE_WINDOW_SEC", "30"))
SHARP_MOVE_PCT = float(os.getenv("SHARP_MOVE_PCT", "0.0012"))
REQUIRE_GAP_REVERSAL = os.getenv("REQUIRE_GAP_REVERSAL", "true").lower() not in ("0", "false", "no")
MAKER_TAKER_SEQUENCE = os.getenv("MAKER_TAKER_SEQUENCE", "false").lower() not in ("0", "false", "no")
USE_WEBSOCKET_FILLS = os.getenv("USE_WEBSOCKET_FILLS", "true").lower() not in ("0", "false", "no")
WS_BASE_URL = os.getenv("WS_BASE_URL", "wss://stream.binancefuture.com" if "testnet" in BASE else "wss://fstream.binance.com")
if not 0 < MARGIN_FRACTION_PER_LEG <= 0.50:
    raise ValueError("MARGIN_FRACTION_PER_LEG must be between 0 and 0.50")
CSV_PATH = os.getenv("CSV_PATH", "data/trades.csv")
EVENT_CSV_PATH = os.getenv("EVENT_CSV_PATH", "data/events.csv")
CSV_FIELDS = [
    "entry_time",
    "exit_time",
    "duration_sec",
    "btc_side",
    "eth_side",
    "btc_qty",
    "eth_qty",
    "entry_gap_pct",
    "exit_gap_pct",
    "exit_reason",
    "pnl_pct",
    "pnl_usd",
]
EVENT_FIELDS = [
    "timestamp",
    "unix_time",
    "event",
    "dry_run",
    "symbol",
    "side",
    "type",
    "quantity",
    "price",
    "reduce_only",
    "time_in_force",
    "order_id",
    "status",
    "executed_qty",
    "btc",
    "eth",
    "window_sec",
    "gap",
    "gap_pct",
    "btc_side",
    "eth_side",
    "btc_qty",
    "eth_qty",
    "available_margin",
    "margin_fraction_per_leg",
    "target_notional",
    "btc_entry_price",
    "eth_entry_price",
    "expected_pnl_usd",
    "estimated_fees_usd",
    "expected_net_pnl_usd",
    "tp_pnl_usd",
    "sl_pnl_usd",
    "btc_bid",
    "btc_ask",
    "eth_bid",
    "eth_ask",
    "btc_move_pct",
    "eth_move_pct",
    "max_poll_move_pct",
    "btc_window_move_pct",
    "eth_window_move_pct",
    "sharp_move_pct",
    "previous_gap",
    "reason",
    "request_csv",
    "response_csv",
    "error_type",
    "status_code",
    "response_body",
]


def log_trade(row: dict) -> None:
    os.makedirs(os.path.dirname(CSV_PATH) or ".", exist_ok=True)
    is_new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def load_day_pnl() -> float:
    if not os.path.exists(CSV_PATH):
        return 0.0
    today = datetime.now(timezone.utc).date()
    total = 0.0
    with open(CSV_PATH, newline="") as f:
        for row in csv.DictReader(f):
            try:
                trade_date = datetime.fromtimestamp(float(row["entry_time"]), timezone.utc).date()
                if trade_date == today:
                    total += float(row.get("pnl_usd", 0) or 0)
            except (KeyError, TypeError, ValueError):
                continue
    return total


def log_event(event: str, **fields) -> None:
    os.makedirs(os.path.dirname(EVENT_CSV_PATH) or ".", exist_ok=True)
    if os.path.exists(EVENT_CSV_PATH):
        with open(EVENT_CSV_PATH, newline="") as existing:
            reader = csv.reader(existing)
            header = next(reader, [])
            if header != EVENT_FIELDS:
                rows = list(reader)
                migrated = [dict(zip(header, row)) for row in rows]
                temporary_path = EVENT_CSV_PATH + ".tmp"
                with open(temporary_path, "w", newline="") as replacement:
                    writer = csv.DictWriter(replacement, fieldnames=EVENT_FIELDS)
                    writer.writeheader()
                    writer.writerows({field: row.get(field, "") for field in EVENT_FIELDS} for row in migrated)
                os.replace(temporary_path, EVENT_CSV_PATH)
    request = fields.get("request", {})
    response = fields.get("response", {})
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "unix_time": time.time(),
        "event": event,
        "dry_run": DRY_RUN,
        **fields,
    }
    record.update({
        "symbol": record.get("symbol", request.get("symbol")),
        "side": record.get("side", request.get("side")),
        "type": record.get("type", request.get("type")),
        "quantity": record.get("quantity", request.get("quantity")),
        "price": record.get("price", request.get("price")),
        "reduce_only": record.get("reduce_only", request.get("reduceOnly")),
        "time_in_force": record.get("time_in_force", request.get("timeInForce")),
        "order_id": record.get("order_id", response.get("orderId")),
        "status": record.get("status", response.get("status")),
        "executed_qty": record.get("executed_qty", response.get("executedQty")),
        "request_csv": json.dumps(request, separators=(",", ":"), default=str),
        "response_csv": json.dumps(response, separators=(",", ":"), default=str),
    })
    row = {field: record.get(field, "") for field in EVENT_FIELDS}
    is_new = not os.path.exists(EVENT_CSV_PATH)
    with open(EVENT_CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EVENT_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def floor_step(qty: float, step: float) -> float:
    return (qty // step) * step


def public_get(path: str, params: dict | None = None):
    headers = {"X-MBX-APIKEY": API_KEY} if API_KEY else {}
    r = requests.get(BASE + path, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


@dataclass(frozen=True)
class SymbolRules:
    price_tick: Decimal
    quantity_step: Decimal
    min_quantity: Decimal
    min_notional: Decimal


_symbol_rules: dict[str, SymbolRules] = {}


def load_symbol_rules() -> None:
    exchange_info = public_get("/fapi/v1/exchangeInfo")
    for symbol_info in exchange_info["symbols"]:
        symbol = symbol_info["symbol"]
        if symbol not in ("BTCUSDT", "ETHUSDT"):
            continue
        filters = {item["filterType"]: item for item in symbol_info["filters"]}
        price_filter = filters["PRICE_FILTER"]
        lot_filter = filters["LOT_SIZE"]
        notional_filter = filters.get("MIN_NOTIONAL", {})
        _symbol_rules[symbol] = SymbolRules(
            price_tick=Decimal(price_filter["tickSize"]),
            quantity_step=Decimal(lot_filter["stepSize"]),
            min_quantity=Decimal(lot_filter["minQty"]),
            min_notional=Decimal(notional_filter.get("notional", "0")),
        )
    if len(_symbol_rules) != 2:
        raise RuntimeError("missing exchange rules for BTCUSDT or ETHUSDT")


def round_down(value: float, step: Decimal) -> Decimal:
    decimal_value = Decimal(str(value))
    return (decimal_value / step).to_integral_value(rounding=ROUND_DOWN) * step


def decimal_text(value: Decimal) -> str:
    return format(value, "f")


def create_listen_key() -> str:
    r = requests.post(BASE + "/fapi/v1/listenKey", headers={"X-MBX-APIKEY": API_KEY}, timeout=10)
    r.raise_for_status()
    return r.json()["listenKey"]


def keepalive_listen_key(listen_key: str) -> None:
    r = requests.put(
        BASE + "/fapi/v1/listenKey",
        headers={"X-MBX-APIKEY": API_KEY},
        params={"listenKey": listen_key},
        timeout=10,
    )
    r.raise_for_status()


_ORDER_STATUS_CACHE_MAX = 200
_order_status_lock = threading.Lock()
_order_status_cache: "OrderedDict[tuple[str, int], dict]" = OrderedDict()


def _store_order_update(symbol: str, order_id: int, status: dict) -> None:
    with _order_status_lock:
        _order_status_cache[(symbol, order_id)] = status
        _order_status_cache.move_to_end((symbol, order_id))
        while len(_order_status_cache) > _ORDER_STATUS_CACHE_MAX:
            _order_status_cache.popitem(last=False)


def _get_cached_order_status(symbol: str, order_id: int) -> dict | None:
    with _order_status_lock:
        return _order_status_cache.get((symbol, order_id))


class UserDataStream:
    """Pushes ORDER_TRADE_UPDATE events into the order-status cache via the private user data stream."""

    def __init__(self):
        self._listen_key: str | None = None
        self._ws = None
        self._stop = threading.Event()
        self._connected = threading.Event()

    def start(self) -> None:
        if websocket is None:
            print("USER_STREAM_UNAVAILABLE", "websocket-client not installed; using REST polling", flush=True)
            return
        try:
            self._listen_key = create_listen_key()
        except Exception as e:
            print("LISTEN_KEY_ERROR", type(e).__name__, flush=True)
            return
        threading.Thread(target=self._run, daemon=True).start()
        threading.Thread(target=self._keepalive_loop, daemon=True).start()

    def is_connected(self) -> bool:
        return self._connected.is_set()

    def stop(self) -> None:
        self._stop.set()
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass

    def _keepalive_loop(self) -> None:
        while not self._stop.wait(1500):
            try:
                keepalive_listen_key(self._listen_key)
            except Exception as e:
                print("LISTEN_KEY_KEEPALIVE_ERROR", type(e).__name__, flush=True)

    def _run(self) -> None:
        url = f"{WS_BASE_URL}/ws/{self._listen_key}"
        while not self._stop.is_set():
            try:
                self._ws = websocket.WebSocketApp(
                    url,
                    on_open=self._on_open,
                    on_close=self._on_close,
                    on_error=self._on_error,
                    on_message=self._on_message,
                )
                self._ws.run_forever(ping_interval=180, ping_timeout=10)
            except Exception as e:
                print("USER_STREAM_ERROR", type(e).__name__, flush=True)
            self._connected.clear()
            if not self._stop.is_set():
                time.sleep(2)

    def _on_open(self, _ws) -> None:
        self._connected.set()
        print("USER_STREAM_CONNECTED", flush=True)

    def _on_close(self, _ws, *_args) -> None:
        self._connected.clear()
        print("USER_STREAM_DISCONNECTED", flush=True)

    def _on_error(self, _ws, error) -> None:
        print("USER_STREAM_WS_ERROR", type(error).__name__, flush=True)

    def _on_message(self, _ws, message: str) -> None:
        try:
            payload = json.loads(message)
        except ValueError:
            return
        if payload.get("e") != "ORDER_TRADE_UPDATE":
            return
        order = payload.get("o", {})
        symbol = order.get("s")
        order_id = order.get("i")
        if symbol is None or order_id is None:
            return
        _store_order_update(symbol, order_id, {
            "symbol": symbol,
            "orderId": order_id,
            "status": order.get("X"),
            "executedQty": order.get("z"),
            "avgPrice": order.get("ap"),
        })


_user_stream: UserDataStream | None = None


def signing_key():
    global _ed25519_key
    if _ed25519_key is None:
        with open(ED25519_KEY_PATH, "rb") as f:
            _ed25519_key = load_pem_private_key(f.read(), password=None)
    return _ed25519_key


def signed_post(path: str, params: dict):
    params = dict(params)
    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = 5000
    query = urllib.parse.urlencode(params)
    sig = base64.b64encode(signing_key().sign(query.encode())).decode()
    headers = {"X-MBX-APIKEY": API_KEY}
    r = requests.post(BASE + path + "?" + query + "&signature=" + urllib.parse.quote(sig, safe=""), headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def configure_symbol(symbol: str) -> None:
    try:
        signed_post("/fapi/v1/marginType", {"symbol": symbol, "marginType": "CROSSED"})
    except requests.HTTPError as error:
        if error.response is None or error.response.json().get("code") != -4046:
            raise
    signed_post("/fapi/v1/leverage", {"symbol": symbol, "leverage": LEVERAGE})


def signed_get(path: str, params: dict | None = None):
    params = dict(params or {})
    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = 5000
    query = urllib.parse.urlencode(params)
    sig = base64.b64encode(signing_key().sign(query.encode())).decode()
    headers = {"X-MBX-APIKEY": API_KEY}
    r = requests.get(BASE + path + "?" + query + "&signature=" + urllib.parse.quote(sig, safe=""), headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def wait_for_fills(orders: list[tuple[str, int]]) -> dict[str, dict]:
    deadline = time.time() + FILL_WAIT_SEC
    statuses = {}
    print("FILL_CHECK_START", [(symbol, order_id) for symbol, order_id in orders], flush=True)
    while time.time() < deadline:
        statuses = {}
        rate_limited = False
        for symbol, order_id in orders:
            cached = _get_cached_order_status(symbol, order_id) if USE_WEBSOCKET_FILLS else None
            if cached is not None:
                statuses[symbol] = cached
                continue
            try:
                statuses[symbol] = signed_get("/fapi/v1/order", {"symbol": symbol, "orderId": order_id})
            except requests.HTTPError as error:
                if error.response is None or error.response.status_code != 429:
                    print("FILL_CHECK_ERROR", type(error).__name__, getattr(error.response, "status_code", None), flush=True)
                    log_event("fill_check_error", error_type=type(error).__name__, status_code=getattr(error.response, "status_code", None), response_body=getattr(error.response, "text", None))
                    raise
                print("FILL_CHECK_RATE_LIMIT", flush=True)
                log_event("fill_check_rate_limit")
                rate_limited = True
                break
        if rate_limited:
            time.sleep(5)
            continue
        print("FILL_CHECK", {symbol: status.get("status") for symbol, status in statuses.items()}, flush=True)
        log_event("fill_check", statuses=statuses)
        if len(statuses) == len(orders) and all(status["status"] == "FILLED" for status in statuses.values()):
            print("FILL_CHECK_COMPLETE", flush=True)
            return statuses
        time.sleep(0.1 if USE_WEBSOCKET_FILLS and _user_stream is not None and _user_stream.is_connected() else 1)
    print("FILL_CHECK_TIMEOUT", {symbol: status.get("status") for symbol, status in statuses.items()}, flush=True)
    log_event("fill_check_timeout", statuses=statuses)
    return statuses



def cancel_open_order(symbol: str, order_id: int) -> None:
    params = {"symbol": symbol, "orderId": order_id}
    response = signed_delete("/fapi/v1/order", params)
    log_event("order_canceled", symbol=symbol, request=params, response=response)


def signed_delete(path: str, params: dict):
    params = dict(params)
    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = 5000
    query = urllib.parse.urlencode(params)
    sig = base64.b64encode(signing_key().sign(query.encode())).decode()
    headers = {"X-MBX-APIKEY": API_KEY}
    r = requests.delete(BASE + path + "?" + query + "&signature=" + urllib.parse.quote(sig, safe=""), headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def ensure_live_account_is_flat() -> None:
    positions = signed_get("/fapi/v2/positionRisk")
    open_orders = signed_get("/fapi/v1/openOrders")
    active_positions = [p for p in positions if abs(float(p["positionAmt"])) > 0]
    if active_positions or open_orders:
        raise RuntimeError("refusing to start with existing positions or open orders")


def available_margin() -> float:
    balances = signed_get("/fapi/v2/balance")
    usdt = next((item for item in balances if item.get("asset") == "USDT"), None)
    if usdt is None:
        raise RuntimeError("USDT balance is unavailable")
    margin = float(usdt["availableBalance"])
    if margin <= 0:
        raise RuntimeError("USDT available margin is not positive")
    return margin


def account_equity() -> float:
    balances = signed_get("/fapi/v2/balance")
    usdt = next((item for item in balances if item.get("asset") == "USDT"), None)
    if usdt is None:
        raise RuntimeError("USDT balance is unavailable")
    equity = float(usdt["balance"])
    if equity <= 0:
        raise RuntimeError("USDT equity is not positive")
    return equity


def mark(symbol: str) -> float:
    data = public_get("/fapi/v1/premiumIndex", {"symbol": symbol})
    return float(data["markPrice"])


def book_ticker(symbol: str) -> tuple[float, float]:
    data = public_get("/fapi/v1/ticker/bookTicker", {"symbol": symbol})
    return float(data["bidPrice"]), float(data["askPrice"])


def estimated_pnl(
    btc_side: str,
    eth_side: str,
    btc_qty: float,
    eth_qty: float,
    btc_entry_price: float,
    eth_entry_price: float,
    btc_bid: float,
    btc_ask: float,
    eth_bid: float,
    eth_ask: float,
) -> float:
    btc_exit_price = btc_bid if btc_side == "BUY" else btc_ask
    eth_exit_price = eth_ask if eth_side == "SELL" else eth_bid
    btc_pnl = (btc_exit_price - btc_entry_price) * btc_qty if btc_side == "BUY" else (btc_entry_price - btc_exit_price) * btc_qty
    eth_pnl = (eth_entry_price - eth_exit_price) * eth_qty if eth_side == "SELL" else (eth_exit_price - eth_entry_price) * eth_qty
    return btc_pnl + eth_pnl


def calculate_net_pnl(
    gross_pnl: float,
    btc_qty: float,
    eth_qty: float,
    btc_entry_price: float,
    eth_entry_price: float,
    btc_exit_price: float,
    eth_exit_price: float,
) -> tuple[float, float]:
    traded_notional = (
        btc_qty * btc_entry_price
        + eth_qty * eth_entry_price
        + btc_qty * btc_exit_price
        + eth_qty * eth_exit_price
    )
    fees = traded_notional * FEE_RATE
    return fees, gross_pnl - fees


@dataclass
class Book:
    t0: float
    btc0: float
    eth0: float


def gap(btc: float, eth: float, book: Book) -> float:
    return (eth / book.eth0 - 1.0) - (btc / book.btc0 - 1.0)


def sizes(btc_px: float, eth_px: float, target_notional: float) -> tuple[float, float]:
    quantities = []
    for symbol, price in (("BTCUSDT", btc_px), ("ETHUSDT", eth_px)):
        rules = _symbol_rules[symbol]
        quantity = round_down(target_notional / price, rules.quantity_step)
        if quantity < rules.min_quantity or quantity <= 0:
            raise ValueError(f"NOTIONAL is too small for {symbol} minimum quantity")
        if rules.min_notional and quantity * Decimal(str(price)) < rules.min_notional:
            raise ValueError(f"NOTIONAL is too small for {symbol} minimum notional")
        quantities.append(float(quantity))
    return tuple(quantities)


def _combine_fill(*orders: dict) -> tuple[float, float]:
    """Weighted-average qty/price across two fills (e.g. a partial maker fill plus its taker fallback)."""
    total_qty = 0.0
    total_notional = 0.0
    for order in orders:
        qty = float(order.get("executedQty", 0) or 0)
        price = float(order.get("avgPrice", 0) or 0)
        total_qty += qty
        total_notional += qty * price
    avg_price = total_notional / total_qty if total_qty > 0 else 0.0
    return total_qty, avg_price


def place(symbol: str, side: str, qty: float, price: float | None, reduce: bool = False, order_type: str = "LIMIT"):
    rules = _symbol_rules[symbol]
    quantity = round_down(qty, rules.quantity_step)
    params = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": decimal_text(quantity),
        "reduceOnly": "true" if reduce else "false",
    }
    if order_type == "LIMIT":
        bid, ask = book_ticker(symbol)
        params["timeInForce"] = "GTX"  # post-only: rests on the book for maker fee, rejected if it would cross
        maker_price = bid if side == "BUY" else ask
        params["price"] = decimal_text(round_down(maker_price, rules.price_tick))
    print("ORDER_POSTING", params, flush=True)
    log_event("order_posting", symbol=symbol, request=params)
    try:
        response = {"dry": True, "orderId": 0, "status": "FILLED", "executedQty": decimal_text(quantity)} if DRY_RUN else signed_post("/fapi/v1/order", params)
    except Exception as error:
        print("ORDER_FAILED", symbol, type(error).__name__, getattr(getattr(error, "response", None), "status_code", None), flush=True)
        log_event(
            "order_error",
            symbol=symbol,
            request=params,
            error_type=type(error).__name__,
            status_code=getattr(getattr(error, "response", None), "status_code", None),
            response_body=getattr(getattr(error, "response", None), "text", None),
        )
        raise
    print("ORDER_ACCEPTED", symbol, response.get("orderId"), response.get("status"), flush=True)
    log_event("order_submitted", symbol=symbol, request=params, response=response)
    return response


def flatten(btc_qty: float, eth_qty: float, btc_side: str, eth_side: str, btc_px: float, eth_px: float):
    orders = []
    if btc_qty > 0:
        order = place("BTCUSDT", "SELL" if btc_side == "BUY" else "BUY", btc_qty, None, True, "MARKET")
        if not DRY_RUN:
            orders.append(("BTCUSDT", order["orderId"]))
    if eth_qty > 0:
        order = place("ETHUSDT", "SELL" if eth_side == "BUY" else "BUY", eth_qty, None, True, "MARKET")
        if not DRY_RUN:
            orders.append(("ETHUSDT", order["orderId"]))
    return orders


def reconcile_flat() -> None:
    positions = signed_get("/fapi/v2/positionRisk")
    open_orders = signed_get("/fapi/v1/openOrders")
    for order in open_orders:
        cancel_open_order(order["symbol"], order["orderId"])
    positions = signed_get("/fapi/v2/positionRisk")
    close_orders = []
    for position in positions:
        quantity = abs(float(position["positionAmt"]))
        if quantity <= 0 or position["symbol"] not in ("BTCUSDT", "ETHUSDT"):
            continue
        side = "SELL" if float(position["positionAmt"]) > 0 else "BUY"
        order = place(position["symbol"], side, quantity, None, True, "MARKET")
        close_orders.append((position["symbol"], order["orderId"]))
    if close_orders:
        wait_for_fills(close_orders)
    remaining = signed_get("/fapi/v2/positionRisk")
    still_open = [p for p in remaining if abs(float(p["positionAmt"])) > 0]
    if still_open:
        raise RuntimeError("unable to confirm flat account after exit")


def enter_sequential_maker_then_taker(
    maker_symbol: str,
    maker_side: str,
    maker_qty: float,
    taker_symbol: str,
    taker_side: str,
    taker_qty: float,
):
    """Post the maker leg only; submit the taker leg after the maker leg is confirmed filled."""
    maker_order = place(maker_symbol, maker_side, maker_qty, None, order_type="LIMIT")
    if DRY_RUN:
        taker_order = place(taker_symbol, taker_side, taker_qty, None, order_type="MARKET")
        return {maker_symbol: maker_order, taker_symbol: taker_order}
    try:
        maker_status = wait_for_fills([(maker_symbol, maker_order["orderId"])]).get(maker_symbol, {})
        if maker_status.get("status") != "FILLED":
            try:
                cancel_open_order(maker_symbol, maker_order["orderId"])
            except requests.HTTPError:
                pass
            maker_status = signed_get("/fapi/v1/order", {"symbol": maker_symbol, "orderId": maker_order["orderId"]})
            filled = float(maker_status.get("executedQty", 0))
            if filled > 0:
                close_side = "SELL" if maker_side == "BUY" else "BUY"
                place(maker_symbol, close_side, filled, None, True, "MARKET")
            log_event("entry_aborted", error_type="MakerLegNotFilled", error=maker_status.get("status"))
            return None
        taker_order = place(taker_symbol, taker_side, taker_qty, None, order_type="MARKET")
        return {maker_symbol: maker_status, taker_symbol: taker_order}
    except Exception:
        # maker leg may be filled or partially filled; force the account back to flat before propagating
        reconcile_flat()
        raise


def main():
    load_symbol_rules()
    if not DRY_RUN:
        ensure_live_account_is_flat()
        for symbol in ("BTCUSDT", "ETHUSDT"):
            configure_symbol(symbol)
        global _user_stream
        _user_stream = UserDataStream()
        _user_stream.start()
    print("dry_run=", DRY_RUN, "notional=", NOTIONAL)
    book = None
    entry_book = None
    in_trade = False
    entry_gap = 0.0
    entry_t = 0.0
    next_entry_t = 0.0
    btc_side = eth_side = ""
    btc_qty = eth_qty = 0.0
    btc_entry_price = eth_entry_price = 0.0
    trade_notional = NOTIONAL
    day_pnl_usd = load_day_pnl()
    day_stop_usd = DAY_STOP_USD
    if not DRY_RUN:
        day_stop_usd = -account_equity() * DAY_STOP_EQUITY_FRACTION
    previous_btc = previous_eth = previous_gap = None
    price_history: deque[tuple[float, float, float]] = deque()

    while True:
        try:
            btc = mark("BTCUSDT")
            eth = mark("ETHUSDT")
        except Exception as e:
            print("price error", e)
            time.sleep(POLL_SEC)
            continue

        now = time.time()
        if book is None or (not in_trade and now - book.t0 >= WINDOW_SEC):
            book = Book(now, btc, eth)
            print(f"anchor  BTC={btc:.2f}  ETH={eth:.2f}")
            log_event("anchor", btc=btc, eth=eth, window_sec=WINDOW_SEC)

        g = gap(btc, eth, book)
        g_since_entry = gap(btc, eth, entry_book) if in_trade and entry_book else None
        print(f"gap={g*100:+.4f}%  BTC={btc:.2f}  ETH={eth:.2f}")
        btc_move = abs(btc / previous_btc - 1.0) if previous_btc else 0.0
        eth_move = abs(eth / previous_eth - 1.0) if previous_eth else 0.0
        price_history.append((now, btc, eth))
        while price_history and now - price_history[0][0] > SHARP_MOVE_WINDOW_SEC:
            price_history.popleft()
        window_btc = [p[1] for p in price_history]
        window_eth = [p[2] for p in price_history]
        btc_window_move = (max(window_btc) - min(window_btc)) / min(window_btc) if len(window_btc) >= 2 else 0.0
        eth_window_move = (max(window_eth) - min(window_eth)) / min(window_eth) if len(window_eth) >= 2 else 0.0
        volatile = (
            btc_move > MAX_POLL_MOVE_PCT or eth_move > MAX_POLL_MOVE_PCT
            or btc_window_move > SHARP_MOVE_PCT or eth_window_move > SHARP_MOVE_PCT
        )
        prior_gap = previous_gap
        gap_reversing = prior_gap is not None and ((g > 0 and g < prior_gap) or (g < 0 and g > prior_gap))
        previous_btc, previous_eth, previous_gap = btc, eth, g

        if not in_trade:
            if day_pnl_usd <= day_stop_usd:
                print("DAY_STOP", day_pnl_usd, flush=True)
                log_event("day_stop", day_pnl_usd=day_pnl_usd, day_stop_usd=day_stop_usd)
                time.sleep(POLL_SEC)
                continue
            if now < next_entry_t:
                time.sleep(POLL_SEC)
                continue
            if volatile:
                log_event(
                    "entry_blocked_volatile",
                    btc_move_pct=btc_move * 100,
                    eth_move_pct=eth_move * 100,
                    max_poll_move_pct=MAX_POLL_MOVE_PCT * 100,
                    btc_window_move_pct=btc_window_move * 100,
                    eth_window_move_pct=eth_window_move * 100,
                    sharp_move_pct=SHARP_MOVE_PCT * 100,
                )
                time.sleep(POLL_SEC)
                continue
            if g >= GAP_ENTER:
                btc_side, eth_side = "BUY", "SELL"
            elif g <= -GAP_ENTER:
                btc_side, eth_side = "SELL", "BUY"
            else:
                time.sleep(POLL_SEC)
                continue
            if REQUIRE_GAP_REVERSAL and not gap_reversing:
                log_event("entry_blocked_no_reversal", gap=g, previous_gap=prior_gap)
                time.sleep(POLL_SEC)
                continue

            try:
                if DRY_RUN:
                    available = None
                    target_notional = NOTIONAL
                else:
                    available = available_margin()
                    target_notional = available * MARGIN_FRACTION_PER_LEG * LEVERAGE
                btc_qty, eth_qty = sizes(btc, eth, target_notional)
            except Exception as e:
                print("SIZING_ERROR", type(e).__name__, str(e), flush=True)
                log_event("sizing_error", error_type=type(e).__name__, error=str(e))
                time.sleep(POLL_SEC)
                continue
            trade_notional = target_notional
            print("ENTER", btc_side, btc_qty, "BTC  ", eth_side, eth_qty, "ETH")
            log_event(
                "entry_signal",
                gap=g,
                gap_pct=g * 100,
                btc=btc,
                eth=eth,
                btc_side=btc_side,
                eth_side=eth_side,
                btc_qty=btc_qty,
                eth_qty=eth_qty,
                available_margin=available,
                margin_fraction_per_leg=MARGIN_FRACTION_PER_LEG,
                target_notional=target_notional,
            )
            btc_order = eth_order = None
            try:
                if MAKER_TAKER_SEQUENCE:
                    result = enter_sequential_maker_then_taker("BTCUSDT", btc_side, btc_qty, "ETHUSDT", eth_side, eth_qty)
                    if result is None:
                        print("ENTRY ABORTED", "maker leg not filled", flush=True)
                        book = Book(time.time(), btc, eth)
                        continue
                    btc_order, eth_order = result["BTCUSDT"], result["ETHUSDT"]
                else:
                    btc_order = place("BTCUSDT", btc_side, btc_qty, btc, order_type=ENTRY_ORDER_TYPE)
                    eth_order = place("ETHUSDT", eth_side, eth_qty, eth, order_type=ENTRY_ORDER_TYPE)
            except Exception as e:
                if not DRY_RUN:
                    for symbol, order, side, quantity in (
                        ("BTCUSDT", btc_order, btc_side, btc_qty),
                        ("ETHUSDT", eth_order, eth_side, eth_qty),
                    ):
                        if order is None:
                            continue
                        status = signed_get("/fapi/v1/order", {"symbol": symbol, "orderId": order["orderId"]})
                        if status["status"] not in ("FILLED", "CANCELED", "EXPIRED", "REJECTED"):
                            try:
                                cancel_open_order(symbol, order["orderId"])
                            except requests.HTTPError:
                                pass
                            status = signed_get("/fapi/v1/order", {"symbol": symbol, "orderId": order["orderId"]})
                        filled = float(status.get("executedQty", 0))
                        if filled > 0:
                            if symbol == "BTCUSDT":
                                flatten(filled, 0, side, eth_side, btc, eth)
                            else:
                                flatten(0, filled, btc_side, side, btc, eth)
                    reconcile_flat()
                log_event("entry_aborted", error_type=type(e).__name__, error=str(getattr(e, "response", None).text) if getattr(e, "response", None) is not None else type(e).__name__)
                print("ENTRY ABORTED", type(e).__name__, getattr(getattr(e, "response", None), "status_code", None))
                book = Book(time.time(), btc, eth)
                continue
            if DRY_RUN:
                statuses = {"BTCUSDT": btc_order, "ETHUSDT": eth_order}
            else:
                statuses = wait_for_fills([
                    ("BTCUSDT", btc_order["orderId"]),
                    ("ETHUSDT", eth_order["orderId"]),
                ])
                log_event("entry_fill_status", statuses=statuses)
                for symbol, order in (("BTCUSDT", btc_order), ("ETHUSDT", eth_order)):
                    if statuses[symbol]["status"] not in ("FILLED", "CANCELED", "EXPIRED", "REJECTED"):
                        try:
                            cancel_open_order(symbol, order["orderId"])
                        except requests.HTTPError:
                            pass
                        statuses[symbol] = signed_get("/fapi/v1/order", {"symbol": symbol, "orderId": order["orderId"]})

                # A maker (GTX) leg that didn't fully fill gets its remainder completed as a
                # MARKET taker order instead of aborting, so a signal always results in a trade.
                if ENTRY_ORDER_TYPE == "LIMIT":
                    for symbol, side, target_qty in (("BTCUSDT", btc_side, btc_qty), ("ETHUSDT", eth_side, eth_qty)):
                        maker_status = statuses[symbol]
                        filled_qty = float(maker_status.get("executedQty", 0) or 0)
                        remaining = float(round_down(target_qty - filled_qty, _symbol_rules[symbol].quantity_step))
                        if remaining <= 0:
                            continue
                        fallback_order = place(symbol, side, remaining, None, order_type="MARKET")
                        fallback_status = wait_for_fills([(symbol, fallback_order["orderId"])])[symbol]
                        log_event("entry_fallback_fill", symbol=symbol, response=fallback_status)
                        combined_qty, combined_price = _combine_fill(maker_status, fallback_status)
                        statuses[symbol] = {
                            **fallback_status,
                            "status": "FILLED" if combined_qty >= target_qty * 0.999 else fallback_status["status"],
                            "executedQty": decimal_text(Decimal(str(combined_qty))),
                            "avgPrice": decimal_text(Decimal(str(combined_price))),
                        }

                btc_filled = float(statuses["BTCUSDT"].get("executedQty", 0))
                eth_filled = float(statuses["ETHUSDT"].get("executedQty", 0))
                if statuses["BTCUSDT"]["status"] != "FILLED" or statuses["ETHUSDT"]["status"] != "FILLED":
                    if btc_filled or eth_filled:
                        flatten(btc_filled, eth_filled, btc_side, eth_side, btc, eth)
                    reconcile_flat()
                    print("ENTRY ABORTED", statuses)
                    book = Book(time.time(), btc, eth)
                    continue
            btc_entry_price = float(statuses["BTCUSDT"].get("avgPrice", 0) or 0)
            eth_entry_price = float(statuses["ETHUSDT"].get("avgPrice", 0) or 0)
            if not DRY_RUN and (btc_entry_price <= 0 or eth_entry_price <= 0):
                raise RuntimeError("filled entry has no average fill price")
            btc_entry_price = btc_entry_price or btc
            eth_entry_price = eth_entry_price or eth
            log_event("entry_prices", btc_entry_price=btc_entry_price, eth_entry_price=eth_entry_price)
            in_trade = True
            entry_gap = g
            entry_t = now
            entry_book = Book(now, btc_entry_price, eth_entry_price)
        else:
            timed = (now - entry_t) >= TIME_STOP_SEC
            force_timed = (now - entry_t) >= MAX_HOLD_SEC
            tp = sl = False
            expected_net_pnl = None
            try:
                btc_bid, btc_ask = book_ticker("BTCUSDT")
                eth_bid, eth_ask = book_ticker("ETHUSDT")
                expected_pnl = estimated_pnl(
                    btc_side, eth_side, btc_qty, eth_qty,
                    btc_entry_price, eth_entry_price,
                    btc_bid, btc_ask, eth_bid, eth_ask,
                )
                btc_exit_price = btc_bid if btc_side == "BUY" else btc_ask
                eth_exit_price = eth_ask if eth_side == "SELL" else eth_bid
                estimated_fees, expected_net_pnl = calculate_net_pnl(
                    expected_pnl,
                    btc_qty, eth_qty,
                    btc_entry_price, eth_entry_price,
                    btc_exit_price, eth_exit_price,
                )
                tp_pnl_usd = trade_notional * TP_PNL_FRACTION
                sl_pnl_usd = -trade_notional * SL_PNL_FRACTION
                log_event(
                    "exit_estimate",
                    expected_pnl_usd=expected_pnl,
                    estimated_fees_usd=estimated_fees,
                    expected_net_pnl_usd=expected_net_pnl,
                    tp_pnl_usd=tp_pnl_usd,
                    sl_pnl_usd=sl_pnl_usd,
                    btc_bid=btc_bid,
                    btc_ask=btc_ask,
                    eth_bid=eth_bid,
                    eth_ask=eth_ask,
                )
                tp = expected_net_pnl >= tp_pnl_usd
                sl = expected_net_pnl <= sl_pnl_usd
            except Exception as e:
                print("EXIT_ESTIMATE_ERROR", type(e).__name__, flush=True)
                log_event("exit_estimate_error", error_type=type(e).__name__, error=str(e))

            # A losing trade gets extra room past TIME_STOP_SEC to recover instead of locking in
            # a loss on the clock alone; SL and MAX_HOLD_SEC remain hard, unconditional backstops.
            timed_exit = timed and expected_net_pnl is not None and expected_net_pnl >= 0

            if tp or sl or timed_exit or force_timed:
                why = "TP" if tp else "SL" if sl else "TIME" if timed_exit else "TIME_MAX"
                if expected_net_pnl is None:
                    fallback_gross = estimated_pnl(
                        btc_side, eth_side, btc_qty, eth_qty,
                        btc_entry_price, eth_entry_price,
                        btc, btc, eth, eth,
                    )
                    _, expected_net_pnl = calculate_net_pnl(
                        fallback_gross, btc_qty, eth_qty,
                        btc_entry_price, eth_entry_price, btc, eth,
                    )
                    log_event("exit_pnl_fallback_used", fallback_pnl_usd=expected_net_pnl)
                # gap_since_entry (not the anchor-relative g) is what actually tracks this position's P&L direction
                print("EXIT", why, f"gap_since_entry={g_since_entry*100:+.4f}%")
                log_event(
                    "exit_signal",
                    reason=why,
                    gap=g_since_entry,
                    gap_pct=g_since_entry * 100,
                    previous_gap=g,
                    btc=btc,
                    eth=eth,
                    btc_qty=btc_qty,
                    eth_qty=eth_qty,
                )
                try:
                    exit_orders = flatten(btc_qty, eth_qty, btc_side, eth_side, btc, eth)
                    if not DRY_RUN:
                        exit_statuses = wait_for_fills(exit_orders)
                        log_event("exit_fill_status", statuses=exit_statuses)
                        if not all(status["status"] == "FILLED" for status in exit_statuses.values()):
                            log_event("exit_reconciliation_required", statuses=exit_statuses)
                        reconcile_flat()
                except Exception as e:
                    print("EXIT_EXECUTION_ERROR", type(e).__name__, flush=True)
                    log_event("exit_execution_error", error_type=type(e).__name__, error=str(e))
                    if not DRY_RUN:
                        reconcile_flat()
                pnl_usd = expected_net_pnl
                pnl_pct = pnl_usd / trade_notional if trade_notional else 0.0
                log_trade({
                    "entry_time": entry_t,
                    "exit_time": now,
                    "duration_sec": round(now - entry_t, 1),
                    "btc_side": btc_side,
                    "eth_side": eth_side,
                    "btc_qty": btc_qty,
                    "eth_qty": eth_qty,
                    "entry_gap_pct": round(entry_gap * 100, 4),
                    "exit_gap_pct": round(g_since_entry * 100, 4),
                    "exit_reason": why,
                    "pnl_pct": round(pnl_pct * 100, 4),
                    "pnl_usd": round(pnl_usd, 2),
                })
                day_pnl_usd += pnl_usd
                log_event("trade_summary", estimated_pnl_usd=pnl_usd, day_pnl_usd=day_pnl_usd)
                in_trade = False
                entry_book = None
                book = Book(now, btc, eth)
                next_entry_t = now + ENTRY_COOLDOWN_SEC

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
