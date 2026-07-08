---
name: t212
description: >
  Manage Trading 212 investment account — view portfolio summary, check cash
  balances, list open positions, place/manage orders (market, limit, stop),
  view historical transactions and dividends, manage investment pies, and
  generate German tax reports (FiFo, Vorabpauschale).
license: MIT
compatibility: Requires Python 3.14+, uv, and Trading 212 API credentials
  (T212_API_KEY_ID, T212_SECRET_KEY).
metadata:
  author: timoh
  version: "1.0.0"
---

## When to use

- **Portfolio check**: "What's my account balance?", "Show my portfolio"
- **Positions**: "List my open positions", "What am I holding?"
- **Orders**: "Place a market buy for 10 shares of AAPL", "Cancel order 12345"
- **History**: "Show my transactions", "What dividends did I receive?"
- **Tax reporting**: "Generate German tax report for 2024"
- **Pies**: "List my pies", "Create a new pie"

## How to invoke

All commands use the `uv run t212` entry point from the repo root.

### Account

```bash
# View account summary (cash, investments, total value)
uv run t212 account summary
```

### Positions

```bash
# List all open positions
uv run t212 positions list

# Filter by ticker
uv run t212 positions list --ticker AAPL_US_EQ
```

### Orders

```bash
# List pending orders
uv run t212 orders list

# Get order by ID
uv run t212 orders get 123456

# Cancel an order
uv run t212 orders cancel 123456

# Place a market order (positive = buy, negative = sell)
uv run t212 orders market --ticker AAPL_US_EQ --quantity 10

# Place a market order with extended hours
uv run t212 orders market --ticker AAPL_US_EQ --quantity 10 --extended-hours
```

### History

```bash
# View historical dividends
uv run t212 history dividends
uv run t212 history dividends --limit 50 --ticker AAPL_US_EQ

# View historical orders
uv run t212 history orders --limit 50

# View transactions
uv run t212 history transactions --limit 50
```

### Metadata

```bash
# List all exchanges
uv run t212 metadata exchanges

# List all tradable instruments
uv run t212 metadata instruments
```

### Pies (deprecated)

```bash
# List all pies
uv run t212 pies list

# Get pie by ID
uv run t212 pies get 12345

# Create a pie from JSON
uv run t212 pies create '{"name":"Tech","instrumentShares":{"AAPL_US_EQ":0.5,"MSFT_US_EQ":0.5}}'

# Update a pie
uv run t212 pies update 12345 '{"goal":15000.0}'

# Delete a pie
uv run t212 pies delete 12345

# Duplicate a pie
uv run t212 pies duplicate 12345 '{"name":"Copy of Tech"}'
```

### German Tax Reporting

```bash
# Classify an instrument (auto-detect fund type)
uv run t212 tax classify IE00BJ0KDQ92

# View local tax config
uv run t212 tax config

# Generate FiFo tax report for a year
uv run t212 tax fifo-report --year 2024
```

### ETF Profile

```bash
# Full ETF profile (holdings, regions, sectors, TER, etc.)
uv run t212 etf profile IE00BJ0KDQ92

# Just top holdings
uv run t212 etf holdings IE00BJ0KDQ92

# Just geographic regions
uv run t212 etf regions IE00BJ0KDQ92

# Just sector breakdown
uv run t212 etf sectors IE00BJ0KDQ92
```

## Configuration

Environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `T212_API_KEY_ID` | Yes | — | Trading 212 API key ID |
| `T212_SECRET_KEY` | Yes | — | Trading 212 secret key |
| `T212_BASE_URL` | No | `https://demo.trading212.com/api/v0` | API endpoint (demo or live) |

**Demo vs Live:**
- Demo: `https://demo.trading212.com/api/v0` (default, paper trading)
- Live: `https://live.trading212.com/api/v0` (real money — set `T212_BASE_URL`)
- Credentials are separate per environment — demo keys won't work on live and vice versa.

## Authentication

The API uses HTTP Basic Auth. Credentials are Base64-encoded as
`api_key_id:secret_key` and sent in the `Authorization` header. The client
handles this automatically.

## API Rate Limits

| Endpoint | Rate Limit |
|----------|-----------|
| Account summary | 1 req / 5s |
| Exchanges | 1 req / 30s |
| Instruments | 1 req / 50s |
| Orders list | 1 req / 5s |
| Place limit/stop/stop-limit | 1 req / 2s |
| Place market order | 50 req / 1m |
| Cancel order | 50 req / 1m |
| Get order by ID | 1 req / 1s |
| Positions | 1 req / 1s |
| Dividends, historical orders, transactions | 6 req / 1m |
| History exports | 1 req / 1m |
| Request export | 1 req / 30s |

## Gotchas

1. **Sell orders use negative quantity**: To sell, pass a negative value
   (e.g., `--quantity -10.5`). Positive = buy, negative = sell.
2. **Orders execute in primary account currency only**: Multi-currency not
   supported via the API.
3. **Pies API is deprecated**: Still functional but will not receive updates.
4. **Market orders may slip**: Final execution price may differ from placement
   price, especially for illiquid instruments.
5. **Rate limits are per-account**, not per-key or per-IP.
6. **Historical data pagination**: Uses cursor-based pagination via
   `nextPagePath`. The CLI handles this automatically in tax reporting.
7. **No idempotency**: The beta API does not guarantee idempotent order
   placement — duplicate requests may create duplicate orders.

## Tax Module (German Tax Reporting)

The CLI includes German tax reporting via FIFO cost basis calculation:

- **Classify instruments**: Auto-detect fund type (thesaurierend/ausschüttend)
  via Finanzfluss scraping
- **FiFo engine**: Computes capital gains using First-In-First-Out matching
- **Config**: Stores instrument classifications locally at `~/.t212/tax_config.yml`
- **Vorabpauschale**: Preliminary lump-sum calculation for German investment
  funds (separate script)

## ETF Data

The CLI fetches ETF data from two sources:

- **justETF** (`justetf.com`): Scraped via `curl_cffi` with Chrome impersonation.
  Provides top 10 holdings (with ISINs), country/region breakdown, sector
  weights, TER, fund size, distribution policy, replication type, and fund
  currency. ISIN-addressable (e.g., `?isin=IE00BJ0KDQ92`).
- **Yahoo Finance** (via `yfinance`): Supplementary data including asset
  allocation (cash/stock/bond), fund operations (expense ratio, turnover, net
  assets), and equity holdings valuations. Uses `curl_cffi.Session(verify=False,
  impersonate="chrome")` as SSL workaround.

**yfinance fix**: The `curl_cffi` library (0.13.0+) has an SSL issue with
`fc.yahoo.com`. The `tax/yahoo_finance.py` module creates a session with
`verify=False` and `impersonate="chrome"` to work around this. The session is
passed to `yf.Ticker(symbol, session=session)`.

## Further reading

- `references/api.md` — Full Trading 212 API reference
- `assets/api.yaml` — OpenAPI specification
- `scripts/t212_cli/` — Source code
- `tests/` — Test suite
