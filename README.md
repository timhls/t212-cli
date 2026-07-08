# Trading 212 CLI

A Python client and CLI for the Trading 212 API.

## Features

- **Account Management**: View account summary, cash balances, and general settings.
- **Instruments**: List available instruments (stocks, ETFs) and exchanges.
- **Positions**: View open positions in your account.
- **Orders**: List, get, cancel, and place market orders. Limit and stop orders are supported by the API but not exposed in the CLI.
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

2. **Environment Variables**: The CLI reads API credentials from environment variables `T212_API_KEY_ID` and `T212_SECRET_KEY`. Optionally, `T212_BASE_URL` can specify the API endpoint (defaults to demo).

### API Environment Selection

By default, the CLI connects to the **Demo** API (`https://demo.trading212.com/api/v0`), which is safe for testing without risking real money.

To use the **Live** API with real money, set the `T212_BASE_URL` environment variable:

```bash
export T212_BASE_URL="https://live.trading212.com/api/v0"
```

You can also set a custom API endpoint if needed:

```bash
export T212_BASE_URL="https://custom.trading212.com/api/v0"
```

**⚠️ Warning**: Always test your commands with the demo API first before using the live API to avoid unintended trades or account changes.

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
uv run mypy .agents/skills/t212/scripts/t212_cli/
```

## Agent Skill

This repository includes an [OpenCode](https://opencode.ai) agent skill at
`.agents/skills/t212/`. The skill enables AI agents to interact with the
Trading 212 API — checking portfolios, placing orders, viewing history, and
generating German tax reports.

See `.agents/skills/t212/SKILL.md` for the full skill definition.
