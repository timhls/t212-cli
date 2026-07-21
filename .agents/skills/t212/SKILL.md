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
  version: "1.2.0"
---

## When to use

- **Portfolio check**: "What's my account balance?", "Show my portfolio"
- **Positions**: "List my open positions", "What am I holding?"
- **Orders**: "Place a market buy for 10 shares of AAPL", "Cancel order 12345",
  "Place a limit order", "Set a stop-loss", "Place a stop-limit order"
- **History**: "Show my transactions", "What dividends did I receive?"
- **Tax reporting**: "Generate German tax report for 2024"
- **Pies**: "List my pies", "Create a new pie", "Analyze pie holdings"
- **ETF analysis**: "Analyze ISIN with justETF and Yahoo Finance", "Get ETF holdings"
- **212 Card transactions**: "Show my card spending", "What did I spend on the card?"
  (Note: the API only exposes anonymous ledger entries — see API Limitations below)

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

# Place a limit order (fills at limitPrice or better; --time-validity DAY|GOOD_TILL_CANCEL)
uv run t212 orders limit --ticker AAPL_US_EQ --quantity 10 --limit-price 180.50
uv run t212 orders limit --ticker AAPL_US_EQ --quantity -10 --limit-price 200 --time-validity GOOD_TILL_CANCEL

# Place a stop order (triggers a market order when stopPrice is hit; negative qty = stop-loss)
uv run t212 orders stop --ticker AAPL_US_EQ --quantity -10 --stop-price 170

# Place a stop-limit order (when stopPrice hit, places a limit order at limitPrice)
uv run t212 orders stop-limit --ticker AAPL_US_EQ --quantity -10 --stop-price 170 --limit-price 169.50
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

### History exports (CSV reports)

Report generation is **asynchronous**: `request` enqueues a report and returns
a `reportId`; poll `list` until `status == Finished`, then read `downloadLink`.

```bash
# List all generated reports and their status
uv run t212 history exports list

# Request a CSV report for a date range (ISO 8601)
uv run t212 history exports request 2024-01-01T00:00:00Z 2024-12-31T23:59:59Z

# Request with --wait: blocks until Finished (or timeout), then prints downloadLink
uv run t212 history exports request 2024-01-01T00:00:00Z 2024-12-31T23:59:59Z --wait

# Exclude sections (orders/dividends/transactions included by default, interest excluded)
uv run t212 history exports request 2024-01-01T00:00:00Z 2024-12-31T23:59:59Z \
    --no-dividends --include-interest
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

# List pie components (instruments) with ISINs
uv run t212 pies components 12345

# Deep-dive analysis: aggregate all underlying ETF holdings,
# weighted by pie share, grouped by company/region/sector
uv run t212 pies analyze 12345

# Analyze with custom top-N holdings limit
uv run t212 pies analyze 12345 --top 50

# Analyze without Yahoo Finance enrichment (justETF only)
uv run t212 pies analyze 12345 --no-yahoo

# Daily value history chart (last 30 days, EUR-normalized)
uv run t212 pies history 12345 --days 30

# Aggregate chart only (skip per-component sub-charts)
uv run t212 pies history 12345 --days 90 --no-per-component

# JSON output (date → value series) for piping into other tools
uv run t212 pies history 12345 --days 60 --json

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

## API Limitations

The Trading 212 Public API is in **beta** and only covers **Invest** and
**Stocks ISA** account types. Key limitations the agent must be aware of:

### No Card Transaction Details

Trading 212 offers a **212 Card** (debit card issued by Paynetics UK Ltd.)
that spends directly from the investment account cash balance. Card
transactions **do appear** in the transaction history endpoint, but the API
provides **no merchant names, categories, locations, or card metadata**.

The `GET /equity/history/transactions` endpoint returns only:

| Field | Description |
|-------|-------------|
| `type` | `WITHDRAW`, `DEPOSIT`, `FEE`, `TRANSFER` |
| `amount` | Signed amount in transaction currency |
| `currency` | Currency code (e.g., `EUR`) |
| `reference` | Internal UUID (not a merchant name) |
| `dateTime` | Settlement timestamp (not real-world purchase time) |

The API description itself says **"Fetch superficial information"**.

**If a user asks about card spending details** (e.g., "find my Alibaba
purchases"), the agent should:
1. Explain that the API does not expose merchant-level data
2. Direct the user to the **T212 app → Cards tab** where merchant names,
   locations, cashback, and fees are visible
3. Mention that CSV/PDF statement exports from the app may contain more detail

### Other API Gaps

- **No multi-currency support**: All values in primary account currency only
- **No CFD account support**: API is Invest/ISA only
- **No card management endpoints**: No API to freeze/unfreeze cards, set PIN,
  view card number, or manage spending pots
- **No real-time price streaming**: Use the position/summary endpoints for
  current values

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
| List pies | 1 req / 30s |
| Pie create / get / update / delete / duplicate | 1 req / 5s |

## Wallet impact schemas

Every `Position` and historical `Fill` carries a `walletImpact` object that
consolidates P/L, FX impact, and taxes. Prefer these fields over any legacy
top-level `ppl` / `fxPpl` (which were removed when the wallet-impact schemas
were introduced).

### `PositionWalletImpact` — `Position.walletImpact`

| Field | Description |
|-------|-------------|
| `currency` | Currency code for all values in this object |
| `currentValue` | Current market value of the position |
| `fxImpact` | P/L impact due to currency rate changes |
| `totalCost` | Total cost paid for the position |
| `unrealizedProfitLoss` | `currentValue − totalCost` |

### `FillWalletImpact` — `Fill.walletImpact`

| Field | Description |
|-------|-------------|
| `currency` | Currency code for all values in this object |
| `fxRate` | FX rate applied to this fill |
| `netValue` | Net value of the fill in account currency |
| `realisedProfitLoss` | Realized P/L for this fill |
| `taxes` | Array of `Tax` objects (see below) |

### `Tax` — items in `FillWalletImpact.taxes`

| Field | Description |
|-------|-------------|
| `chargedAt` | When the tax was charged |
| `currency` | Tax currency code |
| `name` | Enum: `COMMISSION_TURNOVER`, `CURRENCY_CONVERSION_FEE`, `FINRA_FEE`, `FRENCH_TRANSACTION_TAX`, `PTM_LEVY`, `STAMP_DUTY`, `STAMP_DUTY_RESERVE_TAX`, `TRANSACTION_FEE` |
| `quantity` | Tax amount |

The tax/FIFO engine in `tax/calculator.py` reads `fill.walletImpact.taxes` and
`fill.walletImpact.fxRate` to compute German cost basis.

## Order initiation sources

`Order.initiatedFrom` indicates how an order was placed:

| Value | Meaning |
|-------|---------|
| `API` | Placed via this Public API |
| `IOS` / `ANDROID` / `WEB` | Placed from a Trading 212 app |
| `SYSTEM` | System-initiated |
| `AUTOINVEST` | Pie auto-invest rule |
| `INSTRUMENT_AUTOINVEST` | Instrument-level auto-invest rule |

## Gotchas

1. **Sell orders use negative quantity**: To sell, pass a negative value
   (e.g., `--quantity -10.5`). Positive = buy, negative = sell. For CLI
   positional args (orders limit/stop/stop-limit), use `--` to separate
   flags from the negative number, e.g.
   `t212 orders stop -- AAPL -10 170`.
2. **Orders execute in primary account currency only**: Multi-currency not
   supported via the API.
3. **Pies API is deprecated**: Still functional but will not receive updates.
4. **Market orders may slip**: Final execution price may differ from placement
   price, especially for illiquid instruments.
5. **Rate limits are per-account**, not per-key or per-IP.
6. **Historical data pagination**: Uses cursor-based pagination via
   `nextPagePath` (`limit` default 20, max 50). The client provides
   `iter_all_orders()`, `iter_all_dividends()`, `iter_all_transactions()`
   generators that follow `nextPagePath` automatically — the CLI's `tax
   fifo-report` uses this. The bare `history orders|dividends|transactions`
   commands fetch a single page; pass `--cursor` from the previous response's
   `nextPagePath` to page manually.
7. **No idempotency**: The beta API does not guarantee idempotent order
   placement — duplicate requests may create duplicate orders.
8. **Instrument resolution cache**: `resolve_ticker_from_isin()` and
   `resolve_isin_from_ticker()` cache the instruments list after the first
   call (single API request). This avoids rate limits during pie analysis
   and ETF enrichment workflows.
9. **Commodity ETCs have no justETF data**: Synthetic commodity ETCs (e.g.,
   WisdomTree Energy/Agriculture) are not covered by justETF. Use
   `--no-yahoo` to skip the Yahoo Finance fallback if it's not useful.
10. **Pie analyze output**: `pies analyze` returns JSON with `top_holdings`
    (ranked by effective pie weight), `countries`, `sectors`,
    `etf_profiles`, and `components_without_data`. Only top-10 holdings per
    ETF are visible via justETF; the rest is in the undisclosed tail.
11. **Card transactions have no merchant data**: The 212 Card exists as a
    product, but the API exposes card spends only as anonymous `WITHDRAW`
    entries with a UUID reference. No merchant name, category, or location
    is available via the API. Direct users to the T212 app for card
    transaction details.
12. **Transactions endpoint returns superficial data**: The API literally
    describes the endpoint as "superficial information". If a user needs
    detailed transaction data, suggest CSV exports via the app or
    `POST /equity/history/exports` (though exports are also limited to the
    same fields).
13. **Yahoo Finance bare-ISIN lookups return wrong prices**: yfinance
    fuzzy-matches bare ISINs to random unrelated funds. Always resolve via
    a proper exchange-suffixed symbol (e.g. `IWFV.L`, `XDWD.L`, `WNUC.DE`).
    The `tax/yahoo_symbols.py` module handles this with a curated map +
    Yahoo search API fallback.
14. **Yahoo `GBpEUR=X` ignores pence convention**: Despite the name, Yahoo's
    `GBpEUR=X` actually returns the GBP→EUR rate (~1.17), not pence→EUR
    (~0.0118). `tax/history.py:_fetch_fx()` divides GBp rates by 100 to
    correct this.
15. **`.L` suffix ≠ GBp currency**: Some LSE-quoted ETFs are USD-denominated
    (e.g. `XDWD.L`, `IEMA.L`). `tax/history.py` queries
    `ticker.fast_info["currency"]` at runtime rather than assuming based on
    the exchange suffix.
16. **Pie cash not on detailed response**: `get_pie_by_id()` returns no cash
    field. `tax/history.py:fetch_pie_history()` fetches cash via
    `get_pies()` and matches by ID.

## Tax Module (German Tax Reporting)

The CLI includes German tax reporting via FIFO cost basis calculation,
validated against the authoritative tax reference:
[references/german-capital-investment-taxation.md](references/german-capital-investment-taxation.md)
("Die Besteuerung privater Kapitalanlagen", legal stand July 2027).

**All tax calculations in `calculator.py` follow the formulas, rates, and
rules specified in that reference.** When modifying tax code, consult the
reference for the exact legal basis (§20 EStG, §23 EStG, InvStG).

### What the engine computes

- **Classify instruments**: Auto-detect fund type (thesaurierend/ausschüttend)
  via Finanzfluss scraping
- **FiFo engine**: Computes capital gains using First-In-First-Out matching
  (§20 Abs.6 EStG, §23 Abs.1 Satz 1 Nr.2 Satz 3 EStG)
- **Config**: Stores instrument classifications locally at `~/.t212/tax_config.yml`
- **Vorabpauschale**: §18 InvStG preliminary lump-sum calculation for
  thesaurierende/teilthesaurierende Fonds, taxed at year end on first business
  day of the following year

### Key rules implemented (per reference)

| Rule | Legal basis | Reference section |
|------|------------|-----------------|
| Abgeltungsteuer 25% + Soli 5.5% | §32d Abs.1 EStG | "Zinserträge, Dividenden" |
| Kirchensteuer reduction of KeSt | §32d Abs.1 Satz 3 EStG | Tax table (lines 22-27) |
| Sparer-Pauschbetrag €1,000 | §20 Abs.9 EStG | Formula section |
| Aktien losses only offset Aktien gains | §20 Abs.6 Satz 4 EStG | "Verlustverrechnung" |
| §23 Freigrenze €1,000 (all-or-nothing) | §23 Abs.3 Satz 5 EStG | "Physisches Gold" |
| Teilfreistellung 30%/15%/0% | §20 InvStG | "Investmentfonds" |
| Vorabpauschale basiszins + 70% factor | §18 Abs.1 InvStG | Formula section |
| 1/12 rule for mid-year purchases | §18 Abs.2 InvStG | Formula section |
| Vorabpauschale deducted at sale without TFS | §19 Abs.1 Satz 4 InvStG | Formula section |
| FIFO mandatory for crypto | §23 Abs.1 Satz 1 Nr.2 Satz 3 EStG | "Bitcoin" |
| Gold-ETC with delivery = §23 (tax-free >1yr) | BFH VIII R 4/15 | "Gold-ETCs" |

### Basiszins values

| Year | Basiszins | Tax due |
|------|-----------|---------|
| 2025 | 2.53% | 2 Jan 2026 |
| 2026 | 3.20% | 4 Jan 2027 |

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

**Enrichment**: `tax/justetf.py` provides `enrich_profile_with_yahoo()` to fill
gaps in justETF profiles with Yahoo Finance data (asset classes, holdings,
sectors). This is used by both `etf profile` and `pies analyze`.

## Pie Analysis

The `tax/pie_analysis.py` module provides deep-dive analysis of investment pies:

- **`analyze_pie()`**: Fetches underlying ETF holdings via justETF, weights each
  by the component's current pie share, and aggregates across all ETFs. Returns
  a `PieAnalysisResult` with ranked holdings, geographic breakdown, and sector
  breakdown. Handles duplicate companies across ETFs and tracks components
  without data (e.g., commodity ETCs).
- **`enrich_pie_components()`**: Fetches pie detail and resolves each component
  ticker to its ISIN using the client's cached instrument map.

Output includes:
- `top_holdings`: Individual companies ranked by effective pie weight
- `countries`: Pie-weighted geographic exposure
- `sectors`: Pie-weighted sector/industry breakdown
- `etf_profiles`: Per-ETF metadata (name, ISIN, share)
- `components_without_data`: Tickers where no ETF profile was found

## Pie History

The `tax/history.py` module reconstructs daily pie value series — the T212 API
exposes only current snapshots, no historical values endpoint.

- **`fetch_pie_history()`**: Fetches the pie, resolves each component ISIN to a
  Yahoo Finance ticker (via `tax/yahoo_symbols.py`), pulls daily close prices
  via yfinance, FX-normalizes to the target currency, multiplies by current
  owned quantity per component, and aggregates into a daily pie value series.
- **`PieHistory` / `ComponentHistory`**: Dataclasses holding per-component and
  aggregate daily value series as pandas Series.
- **`summary_stats()`**: Returns start/end/min/max/abs_change/pct_change and
  annualized volatility for a value series.

Output of `t212 pies history <id>`:
- Aggregate pie value chart (ASCII line chart via `tax/charts.py`)
- Per-component summary table (start value, latest value, % change, sparkline)
- Optional per-component ASCII line charts

**Assumptions** (per T212 API limitations):
- Quantities held are assumed constant across the window (no historical
  holdings snapshot is available).
- Price return only — dividends not included in the value series.
- Cash inside the pie is treated as a constant baseline.

## Further reading

- `references/api.md` — Full Trading 212 API reference
- `assets/api.yaml` — OpenAPI specification
- `scripts/t212_cli/` — Source code
- `tests/` — Test suite
