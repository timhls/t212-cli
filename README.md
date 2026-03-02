# Trading 212 CLI

A Python client and CLI for the Trading 212 API.

## Features

- **Account Management**: View account summary, cash balances, and general settings.
- **Instruments**: List available instruments (stocks, ETFs) and exchanges.
- **Positions**: View open positions in your account.
- **Orders**: Place, modify, list, and cancel market, limit, and stop orders.
- **Pies**: Create, update, duplicate, and delete investment pies from JSON payloads.
- **History**: View historical events like dividends, exports, orders, and transactions.

## Installation

You can install the package using `uv` (recommended), `pip` or any other Python package manager.

```bash
pip install t212-cli
```

Or using `uv`:

```bash
uv pip install t212-cli
```

## Setup

The CLI requires a Trading 212 API key ID and secret key. You can provide these in two ways:

1. **Environment Variables**: Set the `T212_API_KEY_ID` and `T212_SECRET_KEY` environment variables.

   ```bash
   export T212_API_KEY_ID="your-api-key-id"
   export T212_SECRET_KEY="your-secret-key"
   ```

2. **Configuration File**: A configuration file located at `~/.config/t212-cli/config.json` (or `%APPDATA%\t212-cli\config.json` on Windows).

By default, the CLI connects to the **Live** API (`live.trading212.com`). To use the **Demo** or **Practice** API (`demo.trading212.com`), set the `T212_API_ENV` environment variable:

```bash
export T212_API_ENV="demo"
```

## Usage

The CLI provides several command groups. You can explore them using the `--help` flag:

```bash
t212 --help
```

### Examples

#### View your account summary

```bash
t212 account summary
```

#### List your open positions

```bash
t212 positions list
```

#### List available instruments

```bash
t212 metadata instruments
```

#### Manage investment pies

```bash
t212 pies list
t212 pies create --payload pie.json
t212 pies delete 12345
```

## Development

This project uses [`uv`](https://docs.astral.sh/uv/) for dependency management and tooling.

### Dev Setup

```bash
uv sync
```

### Running Tests

```bash
uv run pytest
```

### Formatting & Linting

```bash
uv run ruff format
uv run ruff check
uv run mypy .
```
