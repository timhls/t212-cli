"""Client for Trading 212's private cards web API.

The 212 Card transaction list in the web app is served by
``https://live.services.trading212.com/rest/cards/v1`` — an internal API that
is *not* part of the public ``/api/v0`` surface and authenticates via browser
session cookies (``TRADING212_SESSION_LIVE`` plus ``LOGIN_TOKEN``), not API
keys.

Verified against the live API (2026-08):

- ``GET /transaction-executions?pageSize=<n>[&cursorId=<id>]`` returns a JSON
  array of transactions, newest first.
- ``pageSize`` must be in ``[0, 50]`` — anything larger is a ``400``.
- ``cursorId`` is the ``id`` of the last item of the previous page; a page
  whose cursor is the oldest existing transaction returns an empty array.
- No special headers are required beyond the session cookies (no Cloudflare
  challenge on this host from a plain HTTP client).
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

import httpx
from t212_cli.client.base import _rate_limit_wait_seconds
from t212_cli.models.cards import CardTransaction

DEFAULT_BASE_URL = "https://live.services.trading212.com/rest/cards/v1"

# Verified live: "Size must be between 0 and 50"
_PAGE_SIZE_MAX = 50
# Safety net against runaway pagination loops if the API misbehaves
_MAX_PAGES = 10_000
# Politeness delay between page fetches (undocumented private API)
_PAGE_DELAY_SECONDS = 0.25

_SESSION_COOKIE_NAMES = ("TRADING212_SESSION_LIVE", "LOGIN_TOKEN")
_PRIMARY_COOKIE = "TRADING212_SESSION_LIVE"

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)


class CardSessionExpiredError(RuntimeError):
    """Raised when the cards API rejects the browser session cookies."""


def _cookies_from_state_file(path: Path) -> dict[str, str]:
    """Extract Trading 212 session cookies from a Playwright storage state file.

    Accepts the JSON written by ``playwright-cli state-save <file>`` (or
    Playwright's ``context.storage_state(path=...)``): a ``cookies`` array
    with ``name``/``value``/``domain`` entries. Only cookies for
    ``trading212.com`` with the known session names are picked up.
    """
    state = json.loads(path.read_text(encoding="utf-8"))
    cookies = state.get("cookies", [])
    if not isinstance(cookies, list):
        raise ValueError(f"No cookies array found in storage state file {path}")
    found: dict[str, str] = {}
    for entry in cookies:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        value = entry.get("value")
        domain = str(entry.get("domain", ""))
        if name in _SESSION_COOKIE_NAMES and value and "trading212.com" in domain:
            found[name] = value
    if _PRIMARY_COOKIE not in found:
        raise ValueError(
            f"No {_PRIMARY_COOKIE} cookie for trading212.com in {path}. "
            "Make sure the browser session is logged in to the live account "
            "and that the state file was saved afterwards."
        )
    return found


def cookie_header_from_state_file(path: Path) -> str:
    """Build a ``Cookie:`` header value from a Playwright storage state file."""
    cookies = _cookies_from_state_file(path)
    return "; ".join(
        f"{name}={cookies[name]}" for name in _SESSION_COOKIE_NAMES if name in cookies
    )


def cookie_header_from_raw(raw: str) -> str:
    """Validate and normalise a raw cookie header value.

    Accepts either a full ``Cookie:`` header or a bare
    ``name=value; name2=value2`` list. Requires the primary session cookie so
    obviously wrong inputs fail fast with a clear message.
    """
    value = raw.removeprefix("Cookie:").strip()
    if _PRIMARY_COOKIE not in value:
        raise ValueError(
            f"Raw cookie string does not contain {_PRIMARY_COOKIE}. "
            "Copy the full Cookie header from an authenticated request to "
            "live.services.trading212.com."
        )
    return value


def resolve_cookie_header(
    cookie_file: Optional[str] = None,
    cookie: Optional[str] = None,
) -> str:
    """Resolve the cookie header from explicit args or environment variables.

    Precedence: ``--cookie-file`` > ``T212_CARDS_COOKIE_FILE`` env var >
    ``--cookie`` raw string > ``T212_CARDS_COOKIES`` env var.
    """
    file_from_env = os.environ.get("T212_CARDS_COOKIE_FILE")
    raw_from_env = os.environ.get("T212_CARDS_COOKIES")

    if cookie_file:
        return cookie_header_from_state_file(Path(cookie_file))
    if file_from_env:
        return cookie_header_from_state_file(Path(file_from_env))
    if cookie:
        return cookie_header_from_raw(cookie)
    if raw_from_env:
        return cookie_header_from_raw(raw_from_env)

    raise ValueError(
        "No Trading 212 session cookies provided. Pass --cookie-file "
        "(Playwright storage state from `playwright-cli state-save <file>`) "
        "or --cookie (raw Cookie header), or set T212_CARDS_COOKIE_FILE / "
        "T212_CARDS_COOKIES."
    )


class CardsClient:
    """HTTP client for the private cards API, authenticated by session cookies."""

    def __init__(
        self,
        cookie_header: str,
        base_url: Optional[str] = None,
        timeout: Optional[float] = 30.0,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("T212_CARDS_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.client = httpx.Client(
            timeout=timeout,
            headers={
                "Cookie": cookie_header,
                "Accept": "application/json",
                "User-Agent": _USER_AGENT,
            },
        )

    def _get(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> httpx.Response:
        """GET with 429 retry, mapping auth failures to CardSessionExpiredError."""
        url = f"{self.base_url}{endpoint}"
        for attempt in range(6):
            response = self.client.get(url, params=params)
            if response.status_code == 429 and attempt < 5:
                time.sleep(min(_rate_limit_wait_seconds(response), 60.0))
                continue
            break
        if response.status_code in (401, 403):
            raise CardSessionExpiredError(
                f"Cards API returned {response.status_code} — the browser "
                "session has expired. Re-login at https://app.trading212.com, "
                "re-export cookies (playwright-cli state-save <file>), retry."
            )
        response.raise_for_status()
        return response

    def get_transactions_page(
        self, *, page_size: int = _PAGE_SIZE_MAX, cursor_id: Optional[int] = None
    ) -> list[CardTransaction]:
        """Fetch a single page of card transactions (newest first)."""
        page_size = max(1, min(page_size, _PAGE_SIZE_MAX))
        params: dict[str, Any] = {"pageSize": page_size}
        if cursor_id is not None:
            params["cursorId"] = cursor_id
        data = self._get("/transaction-executions", params).json()
        return [CardTransaction(**item) for item in data]

    def iter_transactions(
        self,
        start: datetime,
        end: datetime,
        *,
        page_size: int = _PAGE_SIZE_MAX,
    ) -> Iterator[CardTransaction]:
        """Yield transactions with ``start <= timeCreated < end`` (tz-aware).

        The API returns transactions newest-first; pagination walks backwards
        via ``cursorId`` and stops as soon as an item predates ``start`` (or a
        page comes back empty). Transactions newer than ``end`` are skipped.
        Items without a ``timeCreated`` are skipped (cannot be classified).
        """
        cursor: Optional[int] = None
        last_seen: Optional[datetime] = None
        for _page in range(_MAX_PAGES):
            page = self.get_transactions_page(page_size=page_size, cursor_id=cursor)
            if not page:
                return
            oldest_in_page: Optional[datetime] = None
            for tx in page:
                created = tx.timeCreated
                if created is None:
                    continue
                if last_seen is not None and created > last_seen:
                    raise RuntimeError(
                        "Cards API pagination returned out-of-order data "
                        f"(id {tx.id} at {created} after {last_seen}); aborting"
                    )
                if oldest_in_page is None or created < oldest_in_page:
                    oldest_in_page = created
                if created < start:
                    return
                if created < end:
                    yield tx
                last_seen = created
            last_id = page[-1].id
            if last_id == cursor:
                return
            cursor = last_id
            time.sleep(_PAGE_DELAY_SECONDS)
        raise RuntimeError(f"iter_transactions exceeded {_MAX_PAGES} pages; aborting")
