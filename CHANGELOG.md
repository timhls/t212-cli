# CHANGELOG



## v0.1.0 (2026-03-02)

### Build

* build: fix semantic-release build command and update VS Code mypy extension

Updates the semantic-release build command in `pyproject.toml` to install `uv` before building the package, resolving a missing command error in CI. Replaces the deprecated `matangover.mypy` VS Code extension with the official `ms-python.mypy-type-checker`.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f893dd3`](https://github.com/timhls/t212-cli/commit/f893dd3eaccb3daaa729420777b2221376227de6))

* build: add VS Code workspace configuration

- Add .vscode/extensions.json with recommendations for Python, Ruff, and Mypy
- Add .vscode/settings.json configured for uv virtual environments, Ruff formatting, and pytest
- Add .vscode/launch.json for debugging the Typer CLI and Pytest suites ([`cc305ee`](https://github.com/timhls/t212-cli/commit/cc305eefa4c0691de90993602ec5dcc3c4526134))

### Chore

* chore: update VS Code configuration for debugging and tests

- Change launch configuration type to `debugpy` instead of the legacy `python`
- Remove redundant pytest launch config as testing is handled by the Test Explorer natively
- Clean up obsolete `nosetestsEnabled` setting from settings.json

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ab7579d`](https://github.com/timhls/t212-cli/commit/ab7579d36274eb4163fc492d89c70654275f91ed))

* chore: configure Python standard .gitignore and remove cached files

- Add standard Python ignore patterns for __pycache__, virtual environments, and tool caches
- Remove accidentally committed .pyc files from the repository

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`30f677c`](https://github.com/timhls/t212-cli/commit/30f677c82314b88a700d548a3392ad83deedd942))

### Documentation

* docs: add Trading 212 API OpenAPI specification

- Add api.yaml containing the OpenAPI 3.0.0 specification for the Public API

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`62bb26c`](https://github.com/timhls/t212-cli/commit/62bb26c07cba78992c91c153abd96b647ddb16cb))

* docs: add initial Trading 212 API documentation and terms

- Add api.md with Trading 212 Public API reference
- Add API-Terms_EN.pdf for legal terms
- Add .gitignore to exclude environment files like .envrc

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4fe022e`](https://github.com/timhls/t212-cli/commit/4fe022ebb0f48984d8cb519a4bf2690c73795ea0))

### Feature

* feat: add commands to create, update, and duplicate pies from JSON payloads

- Add `t212 pies create &lt;payload&gt;` to create a new pie
- Add `t212 pies update &lt;pie_id&gt; &lt;payload&gt;` to update an existing pie
- Add `t212 pies duplicate &lt;pie_id&gt; &lt;payload&gt;` to duplicate a pie
- Support both raw JSON strings and file paths pointing to JSON files for the payload argument
- Include payload structure examples in command help text

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4811a8a`](https://github.com/timhls/t212-cli/commit/4811a8a44d61e2a6702cadf1ff44661732e582e1))

* feat: add CLI commands for managing investment pies

- Add `t212 pies list` to fetch all pies
- Add `t212 pies get &lt;id&gt;` to fetch a specific pie
- Add `t212 pies delete &lt;id&gt;` to delete a pie

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`27b9e9f`](https://github.com/timhls/t212-cli/commit/27b9e9f2ea09217b13bd8a0c8608b1b2ada6316c))

* feat: implement complete Trading 212 API and CLI commands

- Generate comprehensive Pydantic models from OpenAPI specification
- Implement all API endpoints in Trading212Client wrapper
- Build nested Typer commands for account, history, metadata, orders, pies, and positions
- Ensure types pass strict Mypy validation
- Update CLI tests to cover nested commands ([`0de0da8`](https://github.com/timhls/t212-cli/commit/0de0da82eb73c9cfb86ae88c5b37fc863412a093))

* feat: update authentication to use API Key ID and Secret Key

- Replace TRADING212_API_KEY with T212_API_KEY_ID and T212_SECRET_KEY
- Implement HTTP Basic Authentication with base64 encoded credentials as required by the API

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`6cc0a37`](https://github.com/timhls/t212-cli/commit/6cc0a37da3dbe1facb4e192135d27100a808539d))

* feat: implement foundational CLI and API client structure

- Add project configuration using uv and pyproject.toml
- Set up domain models with Pydantic and base API client with httpx
- Implement base Typer CLI app with an account command
- Set up basic tests using Pytest and typer.testing
- Configure Ruff, Mypy, and Pytest in CI via GitHub Actions
- Configure automated release via Python Semantic Release
- Set up Renovate for dependency management ([`477a7d5`](https://github.com/timhls/t212-cli/commit/477a7d584eb5487fc8b9ed88d2a047baa5932124))

### Fix

* fix: correct account endpoint from /info to /summary

- Update Trading212Client.get_account_info to use the correct API endpoint `/equity/account/summary` instead of `/equity/account/info` which does not exist in the API specification

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c4bce60`](https://github.com/timhls/t212-cli/commit/c4bce60bd6a4f837c63a04248c89e476b3a26b3c))
