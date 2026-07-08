# t212-cli Agent Instructions

Welcome to the `t212-cli` repository! This document outlines the essential commands, guidelines, and conventions for AI coding agents operating within this project.

## 1. Project Overview

`t212-cli` is a Python client and Command Line Interface (CLI) for the Trading 212 API. It uses `uv` for dependency management and tooling, `typer` for the CLI interface, `httpx` for API requests, and `pydantic` for data validation.

## 2. Build, Lint, and Test Commands

We use `uv` exclusively for running all commands. Do not use standard `pip` or `python` commands unless specifically required.

### Testing
- **Run all tests:** `uv run pytest`
- **Run a single test file:** `uv run pytest tests/path/to/test.py`
- **Run a single test function:** `uv run pytest tests/path/to/test.py::test_function_name`
- **Run tests with coverage:** `uv run pytest --cov`

### Linting & Formatting
- **Format code:** `uv run ruff format`
- **Lint code:** `uv run ruff check`
- **Fix linting errors:** `uv run ruff check --fix`

### Type Checking
- **Run type checker:** `uv run mypy .agents/skills/t212/scripts/t212_cli/`
  - *Note:* The project runs `mypy` with `strict = true`. All new code must be fully type-hinted.

### Build and Run
- **Build project:** `uv build`
- **Run the CLI:** `uv run t212 <command>`
- **Example:** `uv run t212 --help`

### Skill Structure
- **Skill path:** `.agents/skills/t212/`
- **Source code:** `.agents/skills/t212/scripts/t212_cli/`
- **Tests:** `.agents/skills/t212/tests/`
- **References:** `.agents/skills/t212/references/`
- **SKILL.md:** `.agents/skills/t212/SKILL.md`

When asked about account info, positions, orders, history, or tax reporting,
the agent should consult the `t212` skill (`.agents/skills/t212/SKILL.md`).

## 3. Code Style Guidelines

### Python Version
- The project target is **Python 3.14**.
- Take advantage of modern Python features appropriate for this version.

### Formatting & Linting
- Code formatting is handled entirely by **Ruff**.
- Line length is configured to **88 characters**.
- Do not introduce formatting tools like `black` or `isort`. Ruff handles both.

### Typing
- **Strict Typing:** All function signatures (arguments and return types) must include type hints.
- Use `typing` module imports (`Optional`, `List`, `Dict`, `Any`) where appropriate.
- When creating data models, use **Pydantic** (`BaseModel`).

### Architecture & Naming Conventions
- **Naming:**
  - Variables, functions, and methods: `snake_case`
  - Classes and Pydantic models: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
- **Structure:**
  - The CLI logic is structured using `typer.Typer` sub-apps (e.g., `account_app`, `orders_app`).
  - Core API logic and requests should be contained in the client module or service layers, keeping the Typer command functions thin.
  - The source package lives at `.agents/skills/t212/scripts/t212_cli/`.
- **Skills:**
  - Skills live in `.agents/skills/<name>/`.
  - `SKILL.md` uses YAML frontmatter (`name`, `description`, `metadata`) followed by Markdown body sections: When to use, How to invoke, Configuration, Gotchas, Further reading.
  - Scripts go in `scripts/`, reference docs in `references/`, tests in `tests/`.
- **Imports:**
  - Group standard library imports first, followed by third-party imports, and finally local `t212_cli` module imports.

### Error Handling
- Use proper `try...except` blocks within the Typer CLI commands.
- Catch exceptions and output user-friendly error messages using `rich.console.Console` (e.g., `console.print(f"[red]Error: {e}[/red]")`).
- Do not expose raw tracebacks to the end-user. Provide clean error messages.

### Testing Conventions
- Use `pytest` for all tests.
- When testing the client or tax calculators, use `unittest.mock.patch` or `MagicMock` to mock external API calls or configuration fetching (`get_instrument_config`).
- Name test files with the `test_` prefix and mirror the `src` directory structure.

## Architecture

### Module Organization

```
.agents/skills/t212/scripts/t212_cli/
├── __main__.py          # Entry point, imports app from cli/main.py
├── cli/
│   ├── main.py          # Main Typer app with sub-apps (account, etf, orders, pies, etc.)
│   └── tax.py           # German tax reporting commands (separate Typer sub-app)
├── client/
│   └── base.py          # Trading212Client - HTTP wrapper for API calls
├── models/
│   └── __init__.py      # Pydantic models for API requests/responses
└── tax/
    ├── calculator.py    # FifoEngine for FIFO tax calculations
    ├── config.py        # Tax configuration loading/saving
    ├── justetf.py       # justETF scraper (holdings, countries, sectors, TER)
    ├── market_data.py   # Re-exports get_historical_price from yahoo_finance
    ├── models.py        # Tax-specific Pydantic models (TaxInstrument, EtfProfile, etc.)
    ├── scraper.py       # Finanzfluss web scraping for instrument classification
    └── yahoo_finance.py # yfinance helper with SSL workaround (session, funds data)
```

### CLI Structure with Typer Sub-apps

The CLI is built using `typer.Typer()` sub-apps:
```python
app = typer.Typer()
app.add_typer(account_app, name="account")
app.add_typer(orders_app, name="orders")
```

### Client Architecture

`Trading212Client` uses Basic Auth with Base64-encoded `api_key_id:secret_key`. Provides `_get()`, `_post()`, `_delete()` helpers. Has `DEMO_URL` and `LIVE_URL` constants.

CLI commands: get client → call method → pretty-print → catch errors.

### Tax Module (German Tax Reporting)

- **FifoEngine**: FIFO calculator for capital gains
- **Market data**: Historical prices via yfinance
- **Config system**: Stores instrument classifications locally
- **Scraper**: Auto-detects fund types (thesaurierend/ausschüttend)

## Release Process

Uses `python-semantic-release` for automated releases via GitHub Actions.

## 4. Dependencies
- **Core Libraries:** Stick to `typer`, `pydantic`, `httpx`, and `rich` for CLI and API operations.
- If instructed to add a new package, modify the `pyproject.toml` or let the user run `uv add <package>`.

## 5. Security & Credentials
- **Never** hardcode API keys or sensitive data.
- The application relies on these environment variables:
  - `T212_API_KEY_ID`: Trading 212 API key ID
  - `T212_SECRET_KEY`: Trading 212 secret key
  - `T212_BASE_URL`: Optional, specify API endpoint URL (defaults to demo: `https://demo.trading212.com/api/v0`)
- Mock these in tests rather than requiring real keys.
