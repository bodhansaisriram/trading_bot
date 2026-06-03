"""
Binance Futures Testnet REST API client.

Handles authentication (HMAC-SHA256 signatures), request construction,
response parsing, and low-level error handling.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger("trading_bot.client")

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
RECV_WINDOW = 5000          # ms — tolerance for timestamp drift


class BinanceAPIError(Exception):
    """Raised when Binance returns a non-2xx HTTP status or a JSON error body."""

    def __init__(self, status_code: int, code: int, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message} (HTTP {status_code})")


class BinanceNetworkError(Exception):
    """Raised on connection timeouts or unrecoverable network failures."""


class BinanceFuturesClient:
    """
    Thin wrapper around the Binance USDT-M Futures REST API (Testnet).

    Parameters
    ----------
    api_key:    Your Testnet API key.
    api_secret: Your Testnet API secret.
    base_url:   Override for the base URL (defaults to Testnet).
    timeout:    HTTP request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        timeout: int = 10,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("Both api_key and api_secret must be provided.")

        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-MBX-APIKEY": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        logger.info("BinanceFuturesClient initialised (base_url=%s)", self._base_url)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Append timestamp + signature to a params dict (mutates in-place)."""
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = RECV_WINDOW
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute an HTTP request and return the parsed JSON response.

        Raises
        ------
        BinanceAPIError    – non-2xx response or JSON `code` error field.
        BinanceNetworkError – connection / timeout failures.
        """
        params = params or {}
        if signed:
            params = self._sign(params)

        url = f"{self._base_url}{endpoint}"
        logger.debug("→ %s %s | params=%s", method.upper(), endpoint, _redact(params))

        try:
            response = self._session.request(
                method,
                url,
                params=params if method.upper() == "GET" else None,
                data=params if method.upper() == "POST" else None,
                timeout=self._timeout,
            )
        except requests.exceptions.Timeout as exc:
            logger.error("Request timed out: %s %s", method, url)
            raise BinanceNetworkError(f"Request timed out after {self._timeout}s.") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error: %s %s — %s", method, url, exc)
            raise BinanceNetworkError(f"Connection failed: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Unexpected request error: %s", exc)
            raise BinanceNetworkError(f"Unexpected network error: {exc}") from exc

        logger.debug("← HTTP %s | body=%s", response.status_code, response.text[:500])

        # Try to parse JSON regardless of status code (Binance puts errors in JSON)
        try:
            data = response.json()
        except ValueError:
            data = {"msg": response.text}

        if not response.ok:
            code = data.get("code", response.status_code)
            msg = data.get("msg", "Unknown error")
            logger.error("API error: code=%s msg=%s (HTTP %s)", code, msg, response.status_code)
            raise BinanceAPIError(response.status_code, code, msg)

        return data

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_server_time(self) -> int:
        """Return Binance server time as Unix ms (also acts as a connectivity check)."""
        data = self._request("GET", "/fapi/v1/time", signed=False)
        return data["serverTime"]

    def get_exchange_info(self) -> Dict[str, Any]:
        """Return full exchange info (symbols, filters, precision, etc.)."""
        return self._request("GET", "/fapi/v1/exchangeInfo", signed=False)

    def get_account(self) -> Dict[str, Any]:
        """Return account balances and positions."""
        return self._request("GET", "/fapi/v2/account")

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: Optional[str] = None,
        stop_price: Optional[str] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Place a new futures order.

        Parameters
        ----------
        symbol       : Trading pair, e.g. 'BTCUSDT'.
        side         : 'BUY' or 'SELL'.
        order_type   : 'MARKET', 'LIMIT', or 'STOP_MARKET'.
        quantity     : Order quantity as a string.
        price        : Required for LIMIT orders.
        stop_price   : Required for STOP_MARKET orders.
        time_in_force: 'GTC', 'IOC', 'FOK' (ignored for MARKET).
        reduce_only  : If True, order can only reduce a position.

        Returns the raw Binance order response dict.
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        if order_type == "LIMIT":
            params["price"] = price
            params["timeInForce"] = time_in_force

        if order_type == "STOP_MARKET":
            params["stopPrice"] = stop_price

        if reduce_only:
            params["reduceOnly"] = "true"

        logger.info(
            "Placing order: symbol=%s side=%s type=%s qty=%s price=%s",
            symbol, side, order_type, quantity, price or stop_price or "N/A",
        )

        response = self._request("POST", "/fapi/v1/order", params=params)
        logger.info("Order placed successfully: orderId=%s status=%s", response.get("orderId"), response.get("status"))
        return response

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an open order by orderId."""
        params = {"symbol": symbol, "orderId": order_id}
        logger.info("Cancelling order: symbol=%s orderId=%s", symbol, order_id)
        return self._request("DELETE", "/fapi/v1/order", params=params)

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Query status of a specific order."""
        params = {"symbol": symbol, "orderId": order_id}
        return self._request("GET", "/fapi/v1/order", params=params)

    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """Return all open orders, optionally filtered by symbol."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/openOrders", params=params)


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------

def _redact(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of params with the signature value masked for safe logging."""
    masked = dict(params)
    if "signature" in masked:
        masked["signature"] = "***"
    return masked
