# t212-cli Developer Guide

A Python client and CLI for the Trading 212 API, built with `uv`, `typer`, `httpx`, and `pydantic`.

## Build, Test, and Lint Commands

All commands use `uv` exclusively. Do not use standard `pip` or `python` commands.

### Testing
- **Run all tests:** `uv run pytest`
- **Run a single test file:** `uv run pytest tests/test_client/test_base.py`
- **Run a single test function:** `uv run pytest tests/test_tax/test_calculator.py::test_fifo_basic`
- **Run with coverage:** `uv run pytest --cov`

### Linting & Formatting
- **Format code:** `uv run ruff format`
- **Lint code:** `uv run ruff check`
- **Fix linting errors:** `uv run ruff check --fix`

### Type Checking
- **Run type checker:** `uv run mypy .`
- **Note:** Project runs with `strict = true`. All new code must be fully type-hinted.

### Build and Run
- **Build project:** `uv build`
- **Run CLI locally:** `uv run t212 <command>`
- **Example:** `uv run t212 account summary`

## Architecture

### Module Organization

```
src/t212_cli/
├── __main__.py          # Entry point, imports app from cli/main.py
├── cli/
│   ├── main.py          # Main Typer app with sub-apps (account, orders, pies, etc.)
│   └── tax.py           # German tax reporting commands (separate Typer sub-app)
├── client/
│   └── base.py          # Trading212Client - HTTP wrapper for API calls
├── models/
│   └── __init__.py      # Pydantic models for API requests/responses
└── tax/
    ├── calculator.py    # FifoEngine for FIFO tax calculations
    ├── config.py        # Tax configuration loading/saving
    ├── market_data.py   # Market data fetching (yfinance)
    ├── models.py        # Tax-specific Pydantic models
    └── scraper.py       # Web scraping for instrument classification
```

### CLI Structure with Typer Sub-apps

The CLI is built using `typer.Typer()` sub-apps, each added to the main app:

```python
app = typer.Typer()  # Main app
account_app = typer.Typer(help="Account summary and commands")
orders_app = typer.Typer(help="Place, modify, or list orders")
# ... etc

app.add_typer(account_app, name="account")
app.add_typer(orders_app, name="orders")
```

Commands are registered to sub-apps using decorators:
```python
@account_app.command("summary")
def account_summary() -> None:
    """Get account summary."""
    client = get_client()
    # ...
```

This creates command hierarchies like: `t212 account summary`, `t212 orders list`, `t212 pies create`

### Client Architecture

`Trading212Client` (in `client/base.py`) handles all API communication:
- Uses Basic Auth with Base64-encoded `api_key_id:secret_key`
- Provides `_get()`, `_post()`, `_delete()` helper methods
- Has `DEMO_URL` and `LIVE_URL` constants for API environments
- Base URL is determined by `T212_BASE_URL` environment variable (defaults to demo)
- Returns typed Pydantic models from all methods

CLI commands should:
1. Call `get_client()` to create authenticated client
2. Call client methods (e.g., `client.get_account_summary()`)
3. Use `pretty_print()` helper to output JSON with `rich.console`
4. Catch exceptions and display user-friendly errors

### Tax Module (German Tax Reporting)

The `tax/` module provides German tax calculations:
- **FifoEngine** (`calculator.py`): FIFO (First-In-First-Out) calculator for capital gains
- **Market data** (`market_data.py`): Fetches historical prices via yfinance
- **Config system** (`config.py`): Stores instrument classifications locally
- **Web scraping** (`scraper.py`): Auto-detects fund types (thesaurierend/ausschüttend)

Key concept: `get_instrument_config(isin)` returns cached or fetched instrument metadata, used by tax calculators to determine fund type and apply German tax rules.

## Code Conventions

### Python Version & Features
- Target: **Python 3.14**
- Use modern Python features appropriate for this version

### Typing (Strict Mode)
- All function signatures must include type hints for arguments and return types
- Use `typing` imports: `Optional`, `List`, `Dict`, `Any`
- Data models use **Pydantic** `BaseModel`
- Never skip type hints; mypy runs in strict mode

### Naming
- Variables, functions, methods: `snake_case`
- Classes, Pydantic models: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`

### Import Order
1. Standard library (e.g., `os`, `json`, `datetime`)
2. Third-party (e.g., `typer`, `httpx`, `pydantic`, `rich`)
3. Local modules (e.g., `t212_cli.client.base`, `t212_cli.models`)

### Error Handling in CLI Commands
- Use `try...except` blocks in CLI command functions
- Output user-friendly errors with `rich.console.Console`:
  ```python
  console.print(f"[red]Error: {e}[/red]")
  ```
- Do not expose raw tracebacks to end users

### Testing Patterns
- Use `pytest` for all tests
- Mock external dependencies with `unittest.mock.patch` or `MagicMock`
- Mock API calls to avoid requiring real API keys
- Mock `get_instrument_config()` in tax calculator tests to avoid fetching real data
- Test file structure mirrors `src/` directory

### Formatting
- Line length: **88 characters**
- **Ruff** handles all formatting and linting
- Do not introduce `black`, `isort`, or other formatters

## Security & Credentials

- Never hardcode API keys or secrets
- Authentication uses environment variables:
  - `T212_API_KEY_ID`: Trading 212 API key ID
  - `T212_SECRET_KEY`: Trading 212 secret key
  - `T212_BASE_URL`: Optional, specify API endpoint URL (defaults to demo: `https://demo.trading212.com/api/v0`)
- Mock credentials in tests rather than requiring real keys

## Dependencies

### Core Libraries
- **typer**: CLI framework
- **pydantic**: Data validation and models
- **httpx**: HTTP client for API requests
- **rich**: Terminal output formatting

### Additional
- **yfinance**: Market data for tax calculations
- **beautifulsoup4** + **lxml**: Web scraping for instrument classification
- **curl-cffi**: CloudFlare bypass for scraping

When adding packages, modify `pyproject.toml` or run `uv add <package>`.

## Release Process

- Uses **python-semantic-release** for automated releases
- Follow **conventional commits** for commit messages:
  - `feat:` for new features (minor version bump)
  - `fix:` for bug fixes (patch version bump)
  - `BREAKING CHANGE:` in footer for major version bump
- Releases are automated via GitHub Actions
