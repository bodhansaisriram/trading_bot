# Binance Futures Testnet Trading Bot

A clean, production-quality Python trading bot for placing **MARKET**, **LIMIT**, and **STOP_MARKET** orders on the [Binance Futures Testnet](https://testnet.binancefuture.com).

---

## Features

- ✅ MARKET and LIMIT order placement (core requirement)
- ✅ STOP_MARKET order placement (**bonus** order type)
- ✅ BUY and SELL sides
- ✅ CLI via `argparse` with full input validation
- ✅ Structured code — separate client / orders / validators / logging layers
- ✅ File logging of every API request, response, and error
- ✅ Exception handling for invalid input, API errors, and network failures
- ✅ Dry-run mode (validate without sending to exchange)
- ✅ Account balance viewer
- ✅ Connectivity ping command

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Package exports
│   ├── client.py            # Binance REST client (auth, signing, HTTP)
│   ├── orders.py            # Order placement logic + display formatting
│   ├── validators.py        # Input validation (symbol, side, type, qty, price)
│   └── logging_config.py   # File + console logging setup
├── cli.py                   # CLI entry point (argparse sub-commands)
├── .env.example             # Template for credentials
├── requirements.txt
├── logs/                    # Auto-created; log files written here
└── README.md
```

---

## Setup

### 1 — Prerequisites

- Python 3.9+
- A Binance Futures Testnet account

### 2 — Get Testnet API credentials

1. Go to [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Sign in (GitHub login available)
3. Navigate to **API Key** in the top menu
4. Click **Generate** — save the key and secret immediately

### 3 — Clone and install

```bash
git clone https://github.com/your-username/trading-bot.git
cd trading_bot

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 4 — Configure credentials

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here
```

Alternatively export them directly:

```bash
export BINANCE_API_KEY=your_key
export BINANCE_API_SECRET=your_secret
```

---

## How to Run

### Test connectivity

```bash
python cli.py ping
```

Expected output:
```
✓  Connected to Binance Futures Testnet — server time: 1736933521843
```

---

### Place a MARKET order

```bash
# BUY 0.001 BTC at market price
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

```
╔══════════════════════════════════════╗
║         ORDER REQUEST SUMMARY         ║
╠══════════════════════════════════════╣
║  Symbol     : BTCUSDT                ║
║  Side       : BUY                    ║
║  Type       : MARKET                 ║
║  Quantity   : 0.001                  ║
╚══════════════════════════════════════╝

╔══════════════════════════════════════╗
║         ORDER RESPONSE DETAILS        ║
╠══════════════════════════════════════╣
║  Order ID    : 4751823019            ║
║  Client OID  : web_Xk9mP2qLvY3nZwR  ║
║  Status      : FILLED                ║
║  Orig Qty    : 0.001                 ║
║  Executed    : 0.001                 ║
║  Avg Price   : 43217.50              ║
║  Updated At  : 1736933522018         ║
╚══════════════════════════════════════╝

✓  Order placed successfully!
```

---

### Place a LIMIT order

```bash
# SELL 0.001 BTC at $45,000 (GTC)
python cli.py place --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 45000
```

---

### Place a STOP_MARKET order (bonus)

```bash
# SELL 0.01 ETH when price drops to $2,200
python cli.py place --symbol ETHUSDT --side SELL --type STOP_MARKET --quantity 0.01 --stop-price 2200
```

---

### Dry-run (validate only, no order sent)

```bash
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001 --dry-run
```

---

### View account balances

```bash
python cli.py account
```

---

### All CLI options

```
python cli.py place --help

options:
  --symbol      Trading pair, e.g. BTCUSDT       (required)
  --side        BUY or SELL                       (required)
  --type        MARKET | LIMIT | STOP_MARKET      (required)
  --quantity    Order quantity                    (required)
  --price       Limit price (LIMIT orders)        (optional)
  --stop-price  Trigger price (STOP_MARKET)       (optional)
  --tif         GTC | IOC | FOK  (default: GTC)   (optional)
  --reduce-only Only reduce an existing position  (flag)
  --dry-run     Validate only, do not submit      (flag)
  --log-level   DEBUG | INFO | WARNING | ERROR    (optional)
  --log-dir     Log output directory              (optional)
```

---

## Logging

Logs are written to `logs/trading_bot_YYYYMMDD.log` automatically.

Each log entry includes:

| Level | What is logged |
|-------|---------------|
| DEBUG | Full API request params (signature redacted) and raw response body |
| INFO  | Order submitted, order ID, status |
| WARNING | API-level errors returned by Binance |
| ERROR | Network failures, unhandled exceptions |

Example log lines:

```
2025-01-15 10:22:01 | INFO     | trading_bot.client | BinanceFuturesClient initialised (base_url=https://testnet.binancefuture.com)
2025-01-15 10:22:01 | DEBUG    | trading_bot.client | → POST /fapi/v1/order | params={'symbol': 'BTCUSDT', ..., 'signature': '***'}
2025-01-15 10:22:02 | DEBUG    | trading_bot.client | ← HTTP 200 | body={"orderId":4751823019,"status":"FILLED",...}
2025-01-15 10:22:02 | INFO     | trading_bot.orders | Order placed successfully: orderId=4751823019 status=FILLED
```

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Missing credentials | Prints helpful message, exits with code 1 |
| Invalid symbol/side/type | `ValueError` with clear message, exits with code 2 |
| LIMIT order missing price | `ValueError` explaining requirement |
| MARKET order supplied price | `ValueError` explaining it's not accepted |
| Binance rejects order | Prints Binance error code + message, exits with code 3 |
| Network timeout | Prints timeout message, exits with code 3 |

---

## Assumptions

- Testnet is USDT-M perpetual futures (`/fapi/v1/order`)
- Default time-in-force for LIMIT orders is `GTC` (configurable via `--tif`)
- `STOP_MARKET` uses `workingType=CONTRACT_PRICE` (Binance default)
- Quantity precision must match Binance's symbol filters; if an order is rejected for step size, reduce decimal places (e.g. `0.001` instead of `0.0012345`)
- Credentials are sourced from environment variables or a `.env` file (never hard-coded)

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `requests` | HTTP client for Binance REST API |
| `python-dotenv` | Load credentials from `.env` file |

---

## Running Tests (optional)

```bash
# Quick validation smoke-test (no network required)
python -c "
from bot.validators import validate_all
r = validate_all(symbol='BTCUSDT', side='buy', order_type='limit', quantity='0.001', price='45000')
print('Validation OK:', r)
"
```
