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
- **Run type checker:** `uv run mypy .`
  - *Note:* The project runs `mypy` with `strict = true`. All new code must be fully type-hinted.

### Build and Run
- **Build project:** `uv build`
- **Run the CLI:** `uv run t212 <command>`
- **Example:** `uv run t212 --help`

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

## 4. Dependencies
- **Core Libraries:** Stick to `typer`, `pydantic`, `httpx`, and `rich` for CLI and API operations.
- If instructed to add a new package, modify the `pyproject.toml` or let the user run `uv add <package>`.

## 5. Security & Credentials
- **Never** hardcode API keys or sensitive data.
- The application relies on `T212_API_KEY_ID` and `T212_SECRET_KEY` environment variables. Mock these in tests rather than requiring real keys.
