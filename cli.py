#!/usr/bin/env python3
"""
cli.py — Command-line interface for the Binance Futures Testnet trading bot.

Usage examples
--------------
# Place a MARKET BUY:
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

# Place a LIMIT SELL:
python cli.py place --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 100000

# Place a STOP_MARKET order (bonus order type):
python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --stop-price 95000

# Dry-run (validate only, no order sent):
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001 --dry-run

# Show account balances:
python cli.py account

Environment variables (or .env file):
  BINANCE_API_KEY     — Testnet API key
  BINANCE_API_SECRET  — Testnet API secret
"""

from __future__ import annotations

import argparse
import os
import sys

# Load .env file if python-dotenv is installed (graceful fallback if not)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from bot.logging_config import setup_logging
from bot.client import BinanceFuturesClient, BinanceAPIError, BinanceNetworkError
from bot.orders import place_order, print_account_balances


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_client() -> BinanceFuturesClient:
    """Build a BinanceFuturesClient from environment variables."""
    api_key    = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()

    if not api_key or not api_secret:
        print(
            "\n✗  Missing credentials.\n"
            "   Set BINANCE_API_KEY and BINANCE_API_SECRET as environment variables\n"
            "   or place them in a .env file in this directory.\n"
        )
        sys.exit(1)

    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret)


# ── Sub-command handlers ──────────────────────────────────────────────────────

def cmd_place(args: argparse.Namespace) -> None:
    """Handle the 'place' sub-command."""
    client = _get_client()

    try:
        place_order(
            client,
            symbol=args.symbol,
            side=args.side,
            order_type=args.type,
            quantity=args.quantity,
            price=args.price,
            stop_price=args.stop_price,
            time_in_force=args.tif,
            reduce_only=args.reduce_only,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        print(f"\n✗  VALIDATION ERROR\n   {exc}\n")
        sys.exit(2)
    except (BinanceAPIError, BinanceNetworkError):
        # Already printed inside place_order; just exit with error code
        sys.exit(3)


def cmd_account(args: argparse.Namespace) -> None:
    """Handle the 'account' sub-command."""
    client = _get_client()
    print_account_balances(client)


def cmd_ping(args: argparse.Namespace) -> None:
    """Handle the 'ping' sub-command — verify connectivity."""
    client = _get_client()
    try:
        server_time = client.get_server_time()
        print(f"\n✓  Connected to Binance Futures Testnet — server time: {server_time}\n")
    except (BinanceAPIError, BinanceNetworkError) as exc:
        print(f"\n✗  Could not reach Binance Testnet: {exc}\n")
        sys.exit(3)


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet trading bot — place MARKET, LIMIT, and STOP_MARKET orders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory to write log files (default: logs/).",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # ── place ────────────────────────────────────────────────
    place_p = subparsers.add_parser(
        "place",
        help="Place a new futures order.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    place_p.add_argument("--symbol",     required=True,  help="Trading pair, e.g. BTCUSDT.")
    place_p.add_argument("--side",       required=True,  choices=["BUY", "SELL"], help="Order side.")
    place_p.add_argument(
        "--type", dest="type", required=True,
        choices=["MARKET", "LIMIT", "STOP_MARKET"],
        help="Order type.",
    )
    place_p.add_argument("--quantity",   required=True,  type=float, help="Order quantity.")
    place_p.add_argument("--price",      default=None,   type=float, help="Limit price (LIMIT orders).")
    place_p.add_argument(
        "--stop-price", dest="stop_price", default=None, type=float,
        help="Stop/trigger price (STOP_MARKET orders).",
    )
    place_p.add_argument(
        "--tif", default="GTC", choices=["GTC", "IOC", "FOK"],
        help="Time-in-force for LIMIT orders.",
    )
    place_p.add_argument(
        "--reduce-only", dest="reduce_only", action="store_true",
        help="Only reduce an existing position.",
    )
    place_p.add_argument(
        "--dry-run", action="store_true",
        help="Validate inputs and print summary but do NOT send to Binance.",
    )
    place_p.set_defaults(func=cmd_place)

    # ── account ──────────────────────────────────────────────
    acct_p = subparsers.add_parser("account", help="Show futures account balances.")
    acct_p.set_defaults(func=cmd_account)

    # ── ping ─────────────────────────────────────────────────
    ping_p = subparsers.add_parser("ping", help="Test connectivity to Binance Testnet.")
    ping_p.set_defaults(func=cmd_ping)

    return parser


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Initialise logging before anything else
    setup_logging(log_dir=args.log_dir, log_level=args.log_level)

    # Dispatch to the selected sub-command
    args.func(args)


if __name__ == "__main__":
    main()
