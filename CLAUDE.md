# t212-cli

## WHAT
A Python client and Command Line Interface (CLI) for the Trading 212 API.

## WHY
To provide developers and users with a fast, scriptable way to manage Trading 212 accounts, instruments, open positions, orders, and investment pies directly from the terminal.

## HOW
This project is built with Python and uses `uv` for dependency management, virtual environments, and running tools. We use `typer` for the CLI interface, `httpx` for API requests, and `pydantic` for data validation.

### Development Workflow

- **Setup**: `uv sync`
- **Run CLI**: `uv run t212 <command>` (e.g., `uv run t212 --help`)
- **Run Tests**: `uv run pytest`
- **Type Checking**: `uv run mypy .`
- **Formatting**: `uv run ruff format`
- **Linting**: `uv run ruff check`

### Important Notes
- The CLI requires `T212_API_KEY_ID` and `T212_SECRET_KEY` for authentication.
- For detailed usage examples and setup instructions, please refer to the [README.md](README.md).
- Releases are automated via `python-semantic-release` using conventional commits.
