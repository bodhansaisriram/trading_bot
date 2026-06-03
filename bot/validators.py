"""
Input validation for order parameters.
All validation functions raise ValueError with descriptive messages on failure.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}

# Binance Futures commonly traded pairs (non-exhaustive; real validation is server-side)
_SYMBOL_SUFFIX_WHITELIST = ("USDT", "BUSD", "BTC", "ETH")


def validate_symbol(symbol: str) -> str:
    """Return uppercased symbol or raise ValueError."""
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Symbol must not be empty.")
    if not any(symbol.endswith(suffix) for suffix in _SYMBOL_SUFFIX_WHITELIST):
        raise ValueError(
            f"Symbol '{symbol}' does not end with a recognised quote asset "
            f"({', '.join(_SYMBOL_SUFFIX_WHITELIST)}). "
            "Check the symbol and try again."
        )
    return symbol


def validate_side(side: str) -> str:
    """Return uppercased side or raise ValueError."""
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValueError(f"Side must be one of {sorted(VALID_SIDES)}, got '{side}'.")
    return side


def validate_order_type(order_type: str) -> str:
    """Return uppercased order type or raise ValueError."""
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Order type must be one of {sorted(VALID_ORDER_TYPES)}, got '{order_type}'."
        )
    return order_type


def _decimal_to_str(d: Decimal) -> str:
    """Convert a Decimal to a plain string without scientific notation or trailing zeros."""
    # normalize() can produce scientific notation for large numbers (e.g. 4.5E+4)
    # format with enough decimal places then strip trailing zeros / dot
    formatted = f"{d:.10f}".rstrip("0").rstrip(".")
    return formatted


def validate_quantity(quantity: str | float) -> str:
    """Return quantity as a clean string or raise ValueError."""
    try:
        qty = Decimal(str(quantity))
    except InvalidOperation:
        raise ValueError(f"Quantity '{quantity}' is not a valid number.")
    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty}.")
    return _decimal_to_str(qty)


def validate_price(price: Optional[str | float], order_type: str) -> Optional[str]:
    """
    Validate price field.

    - LIMIT orders require a positive price.
    - MARKET orders must not supply a price.

    Returns the price as a clean string, or None for MARKET orders.
    """
    order_type = order_type.strip().upper()

    if order_type == "MARKET":
        if price is not None and str(price).strip() not in ("", "0", "0.0"):
            raise ValueError("MARKET orders do not accept a price — omit the --price flag.")
        return None

    if order_type == "LIMIT":
        if price is None or str(price).strip() in ("", "0", "0.0"):
            raise ValueError(f"LIMIT orders require a valid --price.")
        try:
            p = Decimal(str(price))
        except InvalidOperation:
            raise ValueError(f"Price '{price}' is not a valid number.")
        if p <= 0:
            raise ValueError(f"Price must be positive, got {p}.")
        return _decimal_to_str(p)

    if order_type == "STOP_MARKET":
        # STOP_MARKET uses stop_price, not price — silently ignore if supplied
        return None

    return None


def validate_stop_price(stop_price: Optional[str | float], order_type: str) -> Optional[str]:
    """Validate stop_price for STOP_MARKET orders."""
    order_type = order_type.strip().upper()
    if order_type != "STOP_MARKET":
        return None

    if stop_price is None or str(stop_price).strip() in ("", "0", "0.0"):
        raise ValueError("STOP_MARKET orders require a valid --stop-price.")
    try:
        sp = Decimal(str(stop_price))
    except InvalidOperation:
        raise ValueError(f"Stop price '{stop_price}' is not a valid number.")
    if sp <= 0:
        raise ValueError(f"Stop price must be positive, got {sp}.")
    return _decimal_to_str(sp)


def validate_all(
    *,
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: Optional[str | float] = None,
    stop_price: Optional[str | float] = None,
) -> dict:
    """
    Run all validations and return a clean params dict.

    Raises ValueError on the first validation failure encountered.
    """
    clean_symbol = validate_symbol(symbol)
    clean_side = validate_side(side)
    clean_type = validate_order_type(order_type)
    clean_qty = validate_quantity(quantity)
    clean_price = validate_price(price, clean_type)
    clean_stop = validate_stop_price(stop_price, clean_type)

    result = {
        "symbol": clean_symbol,
        "side": clean_side,
        "order_type": clean_type,
        "quantity": clean_qty,
    }
    if clean_price is not None:
        result["price"] = clean_price
    if clean_stop is not None:
        result["stop_price"] = clean_stop

    return result
