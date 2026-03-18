# CHANGELOG



## v0.4.0 (2026-03-18)

### Chore

* chore(vscode): remove python.defaultInterpreterPath

Removes the `python.defaultInterpreterPath` setting from VS Code workspace settings. This setting was causing unresolvable path warnings in the new Python Environment Tools (PET) discovery process. The Python extension now successfully auto-discovers the `.venv` environment anyway.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b17cc65`](https://github.com/timhls/t212-cli/commit/b17cc657b5b5444e6694de4723e416503da9991a))

### Feature

* feat: default to demo environment and add --live flag ([`8335e20`](https://github.com/timhls/t212-cli/commit/8335e20858de4b12f06125552bc4dd7d108bb3af))

### Fix

* fix: add calculator fix ([`d7977ba`](https://github.com/timhls/t212-cli/commit/d7977ba919dce9ba51c899df55a051b753a1faac))

### Test

* test: fix mypy typing errors in test files ([`b95b8a7`](https://github.com/timhls/t212-cli/commit/b95b8a7896d962fd5e32dd78f3af0f1ae1a56665))

### Unknown

* Merge pull request #1 from timhls/copilot/validate-trading-212-api-usage

Validate Trading 212 API usage and fix tax calculation test coverage ([`ee23abd`](https://github.com/timhls/t212-cli/commit/ee23abd01cca6e3fc19937abe8692b20400883a4))

* Validate API usage and verify tax calculation accuracy

- Fix non-standard Python 3 except syntax in config.py: use (E1, E2) tuple form
- Move module-level imports out of function body in cli/tax.py
- Add API client tests: validate Basic auth header encoding, Accept header, URL construction, and auth header presence on GET/POST/DELETE
- Add tax calculator tests: multi-tranche FIFO sell, sonstige gains do not consume aktien_verlusttopf, year_taxable_gains isolation

Co-authored-by: timhls &lt;11960973+timhls@users.noreply.github.com&gt; ([`9bf929f`](https://github.com/timhls/t212-cli/commit/9bf929f710909228f1e7eeb9d02565bd92a7195b))

* Initial plan (no code changes yet)

Co-authored-by: timhls &lt;11960973+timhls@users.noreply.github.com&gt; ([`784a454`](https://github.com/timhls/t212-cli/commit/784a4549efd116a6ffc5e0b83685419c99f18694))

* Initial plan ([`38c9710`](https://github.com/timhls/t212-cli/commit/38c97102bc6526199bbd5d9bdc75125cfbfecf4c))


## v0.3.0 (2026-03-04)

### Feature

* feat(tax): implement FIFO engine and wire to `fifo-report` command

- Implement `FifoEngine` state machine in `calculator.py`
  - Handles tranches, partial sales, and Anschaffungsnebenkosten (fees)
  - Applies ETF Teilfreistellung (TFS) automatically based on local config
  - Segregates losses into Aktienverlusttopf and Allgemeiner Verlusttopf (§20 Abs. 6 EStG)
  - Adds target year tracking logic for localized reports
- Update `t212 tax fifo-report`:
  - Fetch all paginated historical orders from Trading 212 API
  - Auto-classify unknown ISINs silently via Finanzfluss scraper
  - Generate chronologically sorted `TaxEvent` inputs for the FiFo engine
  - Print beautiful Rich tables summarizing Net Taxable Gains and Loss Buckets for the target year
- Fix Mypy static typing issues

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`7fff6c5`](https://github.com/timhls/t212-cli/commit/7fff6c5304d7e5c3896eccc619eb5ee8b8296695))


## v0.2.0 (2026-03-04)

### Build

* build: install and configure pre-commit hooks ([`7968092`](https://github.com/timhls/t212-cli/commit/79680922739784c05d08ee0028e7d4f59a631c85))

* build: fix absolute python path in .python-version

- Change .python-version from an absolute local path (`/opt/homebrew/bin/python3.14`) to `3.14`.
- This fixes CI workflows where the specific macOS homebrew path does not exist.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3d2d846`](https://github.com/timhls/t212-cli/commit/3d2d846ca3a8cc2caebf16b603c35151c2ebd452))

* build: update Python target version to 3.14

- Pin Python version to 3.14.3 using `uv python pin`.
- Update `requires-python` constraint to `&gt;=3.14` in `pyproject.toml`.
- Configure Ruff and Mypy to target Python 3.14.
- Update GitHub Actions `ci.yml` to use `python-version: &#39;3.14&#39;`.
- Resync `uv.lock` with updated constraints and newer wheels matching the new interpreter.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e9b634a`](https://github.com/timhls/t212-cli/commit/e9b634a496b195eaaeead72b5cc43be2ca3643a7))

### Ci

* ci: rename CI workflow and update gitignore

- Rename CI pipeline from &#34;Python CI Pipeline (Free Stack)&#34; to &#34;Build and Test&#34;.
- Add coverage.xml and .coverage to .gitignore to prevent committing coverage reports.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`517e465`](https://github.com/timhls/t212-cli/commit/517e465c25141974a3ba8b382cf5acfc3e32425e))

* ci: adapt and integrate new Python CI Pipeline

- Replaced basic CI pipeline with the provided &#34;Python CI Pipeline (Free Stack)&#34;
- Adapted the pipeline to use `uv` for dependency management instead of `pip`.
- Added `pytest-cov` and `bandit` to dev dependencies in `pyproject.toml`.
- Configured Bandit to scan the `src` directory directly and Pytest to measure coverage of `src`.
- Maintained the existing `mypy` step alongside `ruff` linting and formatting.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`6953c0d`](https://github.com/timhls/t212-cli/commit/6953c0dedcd59b01333273fd2c507e35a357e637))

### Documentation

* docs: update README.md and add CLAUDE.md

- Rewrite README.md with comprehensive Features, Installation, Setup, Usage, and Development sections.
- Update Setup section to reflect requirement for both T212_API_KEY_ID and T212_SECRET_KEY.
- Add CLAUDE.md to establish context engineering guidelines for LLM agents.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8069e26`](https://github.com/timhls/t212-cli/commit/8069e26ad993635581d7fbfb1593e0556a7604e2))

### Feature

* feat(tax): implement German tax reporting module with auto-classification

- Add `tax` command group to CLI
- Implement `TaxInstrument` and `AssetClass` models
- Add `config` manager for persistent local tax settings (`~/.t212/tax_config.yml`)
- Implement `scrape_finanzfluss` using `curl_cffi` to auto-detect ETF/ETC tax status
- Add `market_data` module using `yfinance` for historical prices
- Register `t212 tax` subcommand in main CLI entrypoint

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`de7c4ed`](https://github.com/timhls/t212-cli/commit/de7c4ed4260f8d41fac224b6298b2eb68987b771))

### Style

* style: format test files with ruff

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b082c53`](https://github.com/timhls/t212-cli/commit/b082c53920a904778ad4f11556299752b57ec3c5))

### Test

* test: fix mypy typing errors in test files

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3d6fd1e`](https://github.com/timhls/t212-cli/commit/3d6fd1e4831dc49f5b27a61a6668ad70a94a870a))

* test: fix ruff linting error

- Remove unused `json` import in `tests/test_cli/test_cli_main.py` which was causing the CI pipeline to fail during the Ruff check.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`554afdd`](https://github.com/timhls/t212-cli/commit/554afddcdc2b9497ac05c072cea53a53eeabbe70))

* test: increase test coverage to 99% and pin dependencies

- Add tests for cli main and client base to achieve 99% coverage
- Pin all dependencies in pyproject.toml to exact versions
- Sync uv.lock with pinned dependencies

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`6b445ad`](https://github.com/timhls/t212-cli/commit/6b445ad264f2cfadf9d6ad6132fd8b4bc2c1435a))


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
