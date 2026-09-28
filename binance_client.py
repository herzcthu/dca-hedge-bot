"""
Reusable Binance USDⓈ-M Futures REST + WebSocket client.

Strategy-agnostic: nothing here assumes a specific pair, number of legs, or
trading rule. Handles auth/signing, symbol precision, order placement,
fill confirmation (WebSocket-first with REST fallback), account safety
checks, and the private user-data-stream connection.
"""

from __future__ import annotations

import base64
import json
import threading
import time
import urllib.parse
from collections import OrderedDict
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

import requests
from cryptography.hazmat.primitives.serialization import load_pem_private_key

try:
    import websocket  # websocket-client package
except ImportError:
    websocket = None

import os

from trade_log import DEFAULT_EVENT_FIELDS, CsvLogger

# --- config (override via environment variables) ---
DRY_RUN = os.getenv("DRY_RUN", "true").lower() not in ("0", "false", "no")
BASE = os.getenv("BASE_URL", "https://testnet.binancefuture.com")  # live: https://fapi.binance.com
API_KEY = os.getenv("BINANCE_API_KEY", "")
ED25519_KEY_PATH = os.getenv("BINANCE_ED25519_PRIVATE_KEY_PATH", "")
LEVERAGE = int(os.getenv("LEVERAGE", "10"))
FILL_WAIT_SEC = int(os.getenv("FILL_WAIT_SEC", "15"))
USE_WEBSOCKET_FILLS = os.getenv("USE_WEBSOCKET_FILLS", "true").lower() not in ("0", "false", "no")
WS_BASE_URL = os.getenv("WS_BASE_URL", "wss://stream.binancefuture.com" if "testnet" in BASE else "wss://fstream.binance.com")
EVENT_CSV_PATH = os.getenv("EVENT_CSV_PATH", "data/events.csv")

_ed25519_key = None
_events = CsvLogger(EVENT_CSV_PATH, DEFAULT_EVENT_FIELDS)


def signing_key():
    global _ed25519_key
    if _ed25519_key is None:
        with open(ED25519_KEY_PATH, "rb") as f:
            _ed25519_key = load_pem_private_key(f.read(), password=None)
    return _ed25519_key


def public_get(path: str, params: dict | None = None):
    headers = {"X-MBX-APIKEY": API_KEY} if API_KEY else {}
    r = requests.get(BASE + path, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def _signed_request(method: str, path: str, params: dict):
    params = dict(params)
    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = 5000
    query = urllib.parse.urlencode(params)
    sig = base64.b64encode(signing_key().sign(query.encode())).decode()
    headers = {"X-MBX-APIKEY": API_KEY}
    url = BASE + path + "?" + query + "&signature=" + urllib.parse.quote(sig, safe="")
    r = requests.request(method, url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def signed_get(path: str, params: dict | None = None):
    return _signed_request("GET", path, params or {})


def signed_post(path: str, params: dict):
    return _signed_request("POST", path, params)


def signed_delete(path: str, params: dict):
    return _signed_request("DELETE", path, params)


# --- symbol precision rules ---

@dataclass(frozen=True)
class SymbolRules:
    price_tick: Decimal
    quantity_step: Decimal
    min_quantity: Decimal
    min_notional: Decimal


_symbol_rules: dict[str, SymbolRules] = {}


def load_symbol_rules(symbols: list[str]) -> None:
    exchange_info = public_get("/fapi/v1/exchangeInfo")
    for symbol_info in exchange_info["symbols"]:
        symbol = symbol_info["symbol"]
        if symbol not in symbols:
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
    missing = [s for s in symbols if s not in _symbol_rules]
    if missing:
        raise RuntimeError(f"missing exchange rules for {missing}")


def round_down(value: float, step: Decimal) -> Decimal:
    decimal_value = Decimal(str(value))
    return (decimal_value / step).to_integral_value(rounding=ROUND_DOWN) * step


def decimal_text(value: Decimal) -> str:
    return format(value, "f")


def sizes(prices: dict[str, float], target_notional: float) -> dict[str, float]:
    """Quantity per symbol for a given notional-per-symbol, respecting exchange precision/minimums."""
    quantities = {}
    for symbol, price in prices.items():
        rules = _symbol_rules[symbol]
        quantity = round_down(target_notional / price, rules.quantity_step)
        if quantity < rules.min_quantity or quantity <= 0:
            raise ValueError(f"target_notional is too small for {symbol} minimum quantity")
        if rules.min_notional and quantity * Decimal(str(price)) < rules.min_notional:
            raise ValueError(f"target_notional is too small for {symbol} minimum notional")
        quantities[symbol] = float(quantity)
    return quantities


# --- account / market data ---

def configure_symbol(symbol: str, leverage: int = LEVERAGE) -> None:
    try:
        signed_post("/fapi/v1/marginType", {"symbol": symbol, "marginType": "CROSSED"})
    except requests.HTTPError as error:
        if error.response is None or error.response.json().get("code") != -4046:
            raise
    signed_post("/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})


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


# --- order placement / fills ---

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


def place(symbol: str, side: str, qty: float, price: float | None, reduce: bool = False, order_type: str = "LIMIT", position_side: str | None = None):
    rules = _symbol_rules[symbol]
    quantity = round_down(qty, rules.quantity_step)
    params = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": decimal_text(quantity),
    }
    if position_side:
        params["positionSide"] = position_side
    else:
        params["reduceOnly"] = "true" if reduce else "false"
    if order_type == "LIMIT":
        bid, ask = book_ticker(symbol)
        params["timeInForce"] = "GTX"  # post-only: rests on the book for maker fee, rejected if it would cross
        maker_price = bid if side == "BUY" else ask
        params["price"] = decimal_text(round_down(maker_price, rules.price_tick))
    print("ORDER_POSTING", params, flush=True)
    _events.log("order_posting", symbol=symbol, request_csv=json.dumps(params))
    try:
        response = {"dry": True, "orderId": 0, "status": "FILLED", "executedQty": decimal_text(quantity)} if DRY_RUN else signed_post("/fapi/v1/order", params)
    except Exception as error:
        print("ORDER_FAILED", symbol, type(error).__name__, getattr(getattr(error, "response", None), "status_code", None), flush=True)
        _events.log(
            "order_error",
            symbol=symbol,
            request_csv=json.dumps(params),
            error_type=type(error).__name__,
            status_code=getattr(getattr(error, "response", None), "status_code", None),
            response_body=getattr(getattr(error, "response", None), "text", None),
        )
        raise
    print("ORDER_ACCEPTED", symbol, response.get("orderId"), response.get("status"), flush=True)
    _events.log("order_submitted", symbol=symbol, order_id=response.get("orderId"), status=response.get("status"),
                request_csv=json.dumps(params), response_csv=json.dumps(response, default=str))
    return response


def place_limit(
    symbol: str,
    side: str,
    qty: float,
    price: float,
    reduce: bool = False,
    time_in_force: str = "GTC",
    position_side: str | None = None,
) -> dict:
    """Resting limit at an explicit price (DCA dip / TP). Not post-only GTX."""
    rules = _symbol_rules[symbol]
    quantity = round_down(qty, rules.quantity_step)
    px = round_down(price, rules.price_tick)
    if quantity <= 0 or px <= 0:
        raise ValueError(f"invalid limit {symbol} qty={quantity} px={px}")
    params = {
        "symbol": symbol,
        "side": side,
        "type": "LIMIT",
        "timeInForce": time_in_force,
        "quantity": decimal_text(quantity),
        "price": decimal_text(px),
    }
    if position_side:
        params["positionSide"] = position_side
    else:
        params["reduceOnly"] = "true" if reduce else "false"
    print("ORDER_POSTING", params, flush=True)
    _events.log("order_posting", symbol=symbol, request_csv=json.dumps(params))
    try:
        response = (
            {"dry": True, "orderId": 0, "status": "NEW", "executedQty": "0", "avgPrice": "0"}
            if DRY_RUN
            else signed_post("/fapi/v1/order", params)
        )
    except Exception as error:
        print("ORDER_FAILED", symbol, type(error).__name__, getattr(getattr(error, "response", None), "status_code", None), flush=True)
        _events.log(
            "order_error",
            symbol=symbol,
            request_csv=json.dumps(params),
            error_type=type(error).__name__,
            status_code=getattr(getattr(error, "response", None), "status_code", None),
            response_body=getattr(getattr(error, "response", None), "text", None),
        )
        raise
    print("ORDER_ACCEPTED", symbol, response.get("orderId"), response.get("status"), flush=True)
    _events.log(
        "order_submitted",
        symbol=symbol,
        order_id=response.get("orderId"),
        status=response.get("status"),
        request_csv=json.dumps(params),
        response_csv=json.dumps(response, default=str),
    )
    return response


def cancel_symbol_orders(symbol: str) -> None:
    if DRY_RUN:
        _events.log("order_canceled", symbol=symbol, reason="dry_run_cancel_all")
        return
    try:
        signed_delete("/fapi/v1/allOpenOrders", {"symbol": symbol})
    except requests.HTTPError as error:
        code = None
        if error.response is not None:
            try:
                code = error.response.json().get("code")
            except Exception:
                code = error.response.status_code
        if code in (-2011, 404):
            return
        raise
    _events.log("order_canceled", symbol=symbol, reason="cancel_all")


def usdt_futures_wallet() -> dict[str, float]:
    """USD-M USDT futures wallet. clip/start comes from here, not a frozen $10k."""
    acc = signed_get("/fapi/v2/account")
    wallet = float(acc.get("totalWalletBalance") or 0.0)
    available = float(acc.get("availableBalance") or 0.0)
    margin = float(acc.get("totalMarginBalance") or wallet)
    return {"wallet": wallet, "available": available, "margin": margin}


def position_book(symbol: str) -> dict[str, dict]:
    """LONG and SHORT rows. One-way positions are folded into the side of the sign."""
    empty = {"symbol": symbol, "positionAmt": "0", "entryPrice": "0", "positionSide": "BOTH"}
    rows = signed_get("/fapi/v2/positionRisk", {"symbol": symbol})
    if isinstance(rows, dict):
        rows = [rows]
    book = {"LONG": dict(empty, positionSide="LONG"), "SHORT": dict(empty, positionSide="SHORT")}
    for row in rows:
        if row.get("symbol") != symbol:
            continue
        side = str(row.get("positionSide") or "BOTH")
        amt = float(row.get("positionAmt") or 0)
        if side == "LONG":
            book["LONG"] = row
        elif side == "SHORT":
            book["SHORT"] = row
        elif amt > 0:
            book["LONG"] = row
        elif amt < 0:
            copied = dict(row)
            copied["positionAmt"] = str(abs(amt))
            book["SHORT"] = copied
    return book


def position_risk(symbol: str) -> dict:
    rows = signed_get("/fapi/v2/positionRisk", {"symbol": symbol})
    if isinstance(rows, dict):
        rows = [rows]
    for row in rows:
        if row.get("symbol") == symbol:
            return row
    return {"symbol": symbol, "positionAmt": "0", "entryPrice": "0", "isolatedWallet": "0", "unRealizedProfit": "0"}


def cancel_open_order(symbol: str, order_id: int) -> None:
    params = {"symbol": symbol, "orderId": order_id}
    response = signed_delete("/fapi/v1/order", params)
    _events.log("order_canceled", symbol=symbol, order_id=order_id, response_csv=json.dumps(response, default=str))


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
                    _events.log("fill_check_error", error_type=type(error).__name__,
                                status_code=getattr(error.response, "status_code", None),
                                response_body=getattr(error.response, "text", None))
                    raise
                print("FILL_CHECK_RATE_LIMIT", flush=True)
                _events.log("fill_check_rate_limit")
                rate_limited = True
                break
        if rate_limited:
            time.sleep(5)
            continue
        print("FILL_CHECK", {symbol: status.get("status") for symbol, status in statuses.items()}, flush=True)
        _events.log("fill_check", response_csv=json.dumps(statuses, default=str))
        if len(statuses) == len(orders) and all(status["status"] == "FILLED" for status in statuses.values()):
            print("FILL_CHECK_COMPLETE", flush=True)
            return statuses
        time.sleep(0.1 if USE_WEBSOCKET_FILLS and _user_stream is not None and _user_stream.is_connected() else 1)
    print("FILL_CHECK_TIMEOUT", {symbol: status.get("status") for symbol, status in statuses.items()}, flush=True)
    _events.log("fill_check_timeout", response_csv=json.dumps(statuses, default=str))
    return statuses


def reconcile_flat() -> None:
    """Cancel all open orders and force-close any nonzero futures position via reduce-only MARKET."""
    open_orders = signed_get("/fapi/v1/openOrders")
    for order in open_orders:
        cancel_open_order(order["symbol"], order["orderId"])
    positions = signed_get("/fapi/v2/positionRisk")
    close_orders = []
    for position in positions:
        quantity = abs(float(position["positionAmt"]))
        if quantity <= 0:
            continue
        symbol = position["symbol"]
        if symbol not in _symbol_rules:
            load_symbol_rules([symbol])
        side = "SELL" if float(position["positionAmt"]) > 0 else "BUY"
        order = place(symbol, side, quantity, None, True, "MARKET")
        close_orders.append((symbol, order["orderId"]))
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
            _events.log("entry_aborted", error_type="MakerLegNotFilled", reason=maker_status.get("status"))
            return None
        taker_order = place(taker_symbol, taker_side, taker_qty, None, order_type="MARKET")
        return {maker_symbol: maker_status, taker_symbol: taker_order}
    except Exception:
        # maker leg may be filled or partially filled; force the account back to flat before propagating
        reconcile_flat()
        raise


# --- private user-data-stream (WebSocket fill push notifications) ---

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


def start_user_stream() -> UserDataStream:
    global _user_stream
    _user_stream = UserDataStream()
    _user_stream.start()
    return _user_stream
