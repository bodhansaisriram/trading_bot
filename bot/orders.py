"""
Order placement orchestration.

This module sits between the CLI layer and the low-level API client.
It calls validators, invokes the client, and formats the result for display.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .client import BinanceFuturesClient, BinanceAPIError, BinanceNetworkError
from .validators import validate_all

logger = logging.getLogger("trading_bot.orders")


# ── Pretty-print helpers ────────────────────────────────────────────────────

def _fmt_summary(params: Dict[str, Any]) -> str:
    """Return a multi-line order request summary string."""
    lines = [
        "",
        "╔══════════════════════════════════════╗",
        "║         ORDER REQUEST SUMMARY         ║",
        "╠══════════════════════════════════════╣",
        f"║  Symbol     : {params['symbol']:<23}║",
        f"║  Side       : {params['side']:<23}║",
        f"║  Type       : {params['order_type']:<23}║",
        f"║  Quantity   : {params['quantity']:<23}║",
    ]
    if "price" in params:
        lines.append(f"║  Price      : {params['price']:<23}║")
    if "stop_price" in params:
        lines.append(f"║  Stop Price : {params['stop_price']:<23}║")
    lines += [
        "╚══════════════════════════════════════╝",
        "",
    ]
    return "\n".join(lines)


def _fmt_response(resp: Dict[str, Any]) -> str:
    """Return a multi-line order response details string."""
    order_id    = resp.get("orderId", "N/A")
    status      = resp.get("status", "N/A")
    exec_qty    = resp.get("executedQty", "0")
    orig_qty    = resp.get("origQty", "N/A")
    avg_price   = resp.get("avgPrice") or resp.get("price") or "N/A"
    client_id   = resp.get("clientOrderId", "N/A")
    update_time = resp.get("updateTime", "N/A")

    lines = [
        "",
        "╔══════════════════════════════════════╗",
        "║         ORDER RESPONSE DETAILS        ║",
        "╠══════════════════════════════════════╣",
        f"║  Order ID    : {str(order_id):<22}║",
        f"║  Client OID  : {str(client_id):<22}║",
        f"║  Status      : {str(status):<22}║",
        f"║  Orig Qty    : {str(orig_qty):<22}║",
        f"║  Executed    : {str(exec_qty):<22}║",
        f"║  Avg Price   : {str(avg_price):<22}║",
        f"║  Updated At  : {str(update_time):<22}║",
        "╚══════════════════════════════════════╝",
        "",
    ]
    return "\n".join(lines)


# ── Main entry point ────────────────────────────────────────────────────────

def place_order(
    client: BinanceFuturesClient,
    *,
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: Optional[str | float] = None,
    stop_price: Optional[str | float] = None,
    time_in_force: str = "GTC",
    reduce_only: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Validate inputs, (optionally) place an order, and print formatted output.

    Parameters
    ----------
    client        : Authenticated BinanceFuturesClient instance.
    symbol        : Trading pair symbol, e.g. 'BTCUSDT'.
    side          : 'BUY' or 'SELL'.
    order_type    : 'MARKET', 'LIMIT', or 'STOP_MARKET'.
    quantity      : Order quantity.
    price         : Limit price (LIMIT orders only).
    stop_price    : Trigger price (STOP_MARKET orders only).
    time_in_force : 'GTC' | 'IOC' | 'FOK' (default 'GTC').
    reduce_only   : Only reduce an existing position.
    dry_run       : If True, validate and print summary but do NOT send to API.

    Returns
    -------
    The raw Binance API response dict, or an empty dict for dry-run.

    Raises
    ------
    ValueError          – Input validation failure.
    BinanceAPIError     – Binance rejected the order.
    BinanceNetworkError – Connectivity problem.
    """
    # 1. Validate
    clean = validate_all(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        stop_price=stop_price,
    )

    # 2. Print request summary
    print(_fmt_summary(clean))

    if dry_run:
        print("⚠  DRY-RUN mode — order was NOT sent to the exchange.\n")
        logger.info("Dry-run: order not submitted. params=%s", clean)
        return {}

    # 3. Submit to API
    try:
        response = client.place_order(
            symbol=clean["symbol"],
            side=clean["side"],
            order_type=clean["order_type"],
            quantity=clean["quantity"],
            price=clean.get("price"),
            stop_price=clean.get("stop_price"),
            time_in_force=time_in_force,
            reduce_only=reduce_only,
        )
    except BinanceAPIError as exc:
        logger.error("Order placement failed: %s", exc)
        print(f"\n✗  ORDER FAILED\n   Binance error {exc.code}: {exc.message}\n")
        raise
    except BinanceNetworkError as exc:
        logger.error("Network error during order placement: %s", exc)
        print(f"\n✗  NETWORK ERROR\n   {exc}\n")
        raise

    # 4. Print response
    print(_fmt_response(response))
    print("✓  Order placed successfully!\n")
    return response


# ── Account info helper ─────────────────────────────────────────────────────

def print_account_balances(client: BinanceFuturesClient) -> None:
    """Fetch and print non-zero USDT/BUSD balances from the futures account."""
    try:
        account = client.get_account()
    except (BinanceAPIError, BinanceNetworkError) as exc:
        print(f"✗  Could not retrieve account info: {exc}\n")
        return

    assets = [
        a for a in account.get("assets", [])
        if float(a.get("walletBalance", 0)) > 0
    ]

    print("\n╔══════════════════════════════════════╗")
    print("║           ACCOUNT BALANCES            ║")
    print("╠══════════════════════════════════════╣")
    if not assets:
        print("║  (no non-zero balances found)         ║")
    for a in assets:
        name = a.get("asset", "?")
        bal  = float(a.get("walletBalance", 0))
        upnl = float(a.get("unrealizedProfit", 0))
        print(f"║  {name:<6}: wallet={bal:<10.4f} uPnL={upnl:<9.4f}║")
    print("╚══════════════════════════════════════╝\n")
