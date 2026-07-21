import httpx
import base64
import os
import time
import urllib.parse
from typing import Any, Iterator, Optional, List
from t212_cli.models import (
    AccountSummary,
    PaginatedResponseHistoryDividendItem,
    ReportResponse,
    PublicReportRequest,
    EnqueuedReportResponse,
    PaginatedResponseHistoricalOrder,
    PaginatedResponseHistoryTransactionItem,
    Exchange,
    TradableInstrument,
    Order,
    LimitRequest,
    MarketRequest,
    StopRequest,
    StopLimitRequest,
    AccountBucketResultResponse,
    AccountBucketInstrumentsDetailedResponse,
    PieRequest,
    DuplicateBucketRequest,
    Position,
    HistoricalOrder,
    HistoryDividendItem,
    HistoryTransactionItem,
)

# Per spec: "Max items: 50" on /history/orders, /history/dividends, /history/transactions
_HISTORY_LIMIT_MAX = 50
_HISTORY_LIMIT_MIN = 1
# Safety guard against infinite pagination loops if the API misbehaves
_MAX_PAGINATION_PAGES = 10_000
# 429 rate-limit retry behaviour (spec: per-account limits on every endpoint)
_RATE_LIMIT_MAX_RETRIES = 5
_RATE_LIMIT_INITIAL_BACKOFF = 5.0
_RATE_LIMIT_MAX_BACKOFF = 60.0


def _validate_limit(limit: int) -> int:
    """Clamp ``limit`` for the cursor-paginated history endpoints to ``[1, 50]``.

    The Trading 212 spec documents ``Max items: 50`` on
    ``/equity/history/{orders,dividends,transactions}``. Values outside the
    valid range are silently clamped rather than raising so callers do not need
    to pre-validate.
    """
    if limit < _HISTORY_LIMIT_MIN:
        return _HISTORY_LIMIT_MIN
    if limit > _HISTORY_LIMIT_MAX:
        return _HISTORY_LIMIT_MAX
    return limit


def _cursor_from_next_page_path(next_page_path: str) -> Optional[str]:
    """Extract the ``cursor`` query param from a ``nextPagePath`` value.

    The spec instructs callers to reuse the *entire* ``nextPagePath`` string
    for the next request. Since this client rebuilds params from
    ``cursor``/``limit``/etc., we parse the cursor out instead. Returns
    ``None`` if the path has no ``cursor`` param.
    """
    parsed = urllib.parse.urlparse(next_page_path)
    query = urllib.parse.parse_qs(parsed.query)
    values = query.get("cursor")
    return values[0] if values else None


def _rate_limit_wait_seconds(response: httpx.Response) -> float:
    """Compute how long to wait before retrying after a 429 response.

    The Trading 212 spec exposes:
    - ``Retry-After``: seconds until *one* request slot frees up. Often too
      optimistic when bursting is exhausted.
    - ``x-ratelimit-reset``: Unix timestamp when the window fully resets and
      ``x-ratelimit-limit`` requests become available again.

    Prefer ``x-ratelimit-reset`` (full reset) to avoid re-hitting 429 on
    every retry; fall back to ``Retry-After`` if missing; otherwise use
    exponential backoff.
    """
    reset_ts = response.headers.get("x-ratelimit-reset")
    if reset_ts:
        try:
            wait = max(0.0, float(reset_ts) - time.time()) + 1.0
            if wait > 0:
                return wait
        except ValueError:
            pass
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return _RATE_LIMIT_INITIAL_BACKOFF


class Trading212Client:
    DEMO_URL = "https://demo.trading212.com/api/v0"
    LIVE_URL = "https://live.trading212.com/api/v0"

    def __init__(
        self,
        api_key_id: str,
        secret_key: str,
        base_url: Optional[str] = None,
        timeout: Optional[float] = 30.0,
    ):
        self.api_key_id = api_key_id
        self.secret_key = secret_key
        # Use provided base_url, or T212_BASE_URL env var, or default to DEMO_URL
        self.base_url = base_url or os.environ.get("T212_BASE_URL", self.DEMO_URL)
        self.timeout = timeout

        credentials_string = f"{api_key_id}:{secret_key}"
        encoded_credentials = base64.b64encode(
            credentials_string.encode("utf-8")
        ).decode("utf-8")

        self.headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Accept": "application/json",
        }

        # Create reusable HTTP client with timeout and connection pooling
        self.client = httpx.Client(timeout=timeout, headers=self.headers)

        # Lazy-loaded instrument caches (populated on first access)
        self._instruments_cache: Optional[List[TradableInstrument]] = None
        self._ticker_to_isin: Optional[dict[str, str]] = None
        self._isin_to_ticker: Optional[dict[str, str]] = None

    def _request_with_rate_limit_retry(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """Issue an HTTP request, retrying on 429 with Retry-After / backoff.

        Dispatches to the underlying client's ``get``/``post``/``delete``
        methods (not the generic ``request``) so callers and tests mocking
        those individual methods keep working.

        The Trading 212 spec documents per-account rate limits on every
        endpoint (e.g. 6 req/min on history endpoints). On 429 the response
        carries a ``Retry-After`` header (seconds) and ``x-ratelimit-reset``
        (Unix timestamp when the window fully resets). The reset timestamp is
        authoritative for long windows; ``Retry-After`` is often optimistic.
        Capped at ``_RATE_LIMIT_MAX_RETRIES`` attempts.
        """
        method_lower = method.lower()
        http_method = getattr(self.client, method_lower)
        for attempt in range(_RATE_LIMIT_MAX_RETRIES + 1):
            response: httpx.Response = http_method(url, **kwargs)
            if response.status_code != 429 or attempt == _RATE_LIMIT_MAX_RETRIES:
                response.raise_for_status()
                return response
            wait = _rate_limit_wait_seconds(response)
            time.sleep(min(wait, _RATE_LIMIT_MAX_BACKOFF))
        # Unreachable: loop returns on the last attempt, but satisfy mypy.
        raise RuntimeError("rate-limit retry loop exhausted")

    def _get(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        return self._request_with_rate_limit_retry("GET", url, params=params)

    def _post(
        self, endpoint: str, json_data: Optional[dict[str, Any]] = None
    ) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        return self._request_with_rate_limit_retry("POST", url, json=json_data)

    def _delete(self, endpoint: str) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        return self._request_with_rate_limit_retry("DELETE", url)

    # 1. Accounts
    def get_account_summary(self) -> AccountSummary:
        response = self._get("/equity/account/summary")
        return AccountSummary(**response.json())

    # 2. Historical events
    def get_historical_dividends(
        self,
        limit: int = 20,
        cursor: Optional[str] = None,
        ticker: Optional[str] = None,
    ) -> PaginatedResponseHistoryDividendItem:
        params: dict[str, Any] = {"limit": _validate_limit(limit)}
        if cursor is not None:
            params["cursor"] = cursor
        if ticker:
            params["ticker"] = ticker
        return PaginatedResponseHistoryDividendItem(
            **self._get("/equity/history/dividends", params).json()
        )

    def get_historical_exports(self) -> List[ReportResponse]:
        return [
            ReportResponse(**x) for x in self._get("/equity/history/exports").json()
        ]

    def request_historical_export(
        self, request: PublicReportRequest
    ) -> EnqueuedReportResponse:
        return EnqueuedReportResponse(
            **self._post(
                "/equity/history/exports", request.model_dump(exclude_none=True)
            ).json()
        )

    def get_historical_orders(
        self,
        limit: int = 20,
        cursor: Optional[str] = None,
        ticker: Optional[str] = None,
    ) -> PaginatedResponseHistoricalOrder:
        params: dict[str, Any] = {"limit": _validate_limit(limit)}
        if cursor is not None:
            params["cursor"] = cursor
        if ticker:
            params["ticker"] = ticker
        return PaginatedResponseHistoricalOrder(
            **self._get("/equity/history/orders", params).json()
        )

    def get_historical_transactions(
        self, limit: int = 20, cursor: Optional[str] = None, time: Optional[str] = None
    ) -> PaginatedResponseHistoryTransactionItem:
        params: dict[str, Any] = {"limit": _validate_limit(limit)}
        if cursor:
            params["cursor"] = cursor
        if time:
            params["time"] = time
        return PaginatedResponseHistoryTransactionItem(
            **self._get("/equity/history/transactions", params).json()
        )

    # 2b. Auto-pagination generators following nextPagePath until exhausted.
    def iter_all_orders(
        self,
        *,
        limit: int = _HISTORY_LIMIT_MAX,
        ticker: Optional[str] = None,
    ) -> Iterator[HistoricalOrder]:
        """Yield every historical order, transparently following ``nextPagePath``.

        Implements the cursor-paginated workflow described in the spec so
        callers do not have to. Raises ``RuntimeError`` if the API returns more
        than ``_MAX_PAGINATION_PAGES`` pages (safety net for misbehaviour).
        """
        cursor: Optional[str] = None
        pages = 0
        while True:
            pages += 1
            if pages > _MAX_PAGINATION_PAGES:
                raise RuntimeError(
                    f"iter_all_orders exceeded {_MAX_PAGINATION_PAGES} pages; aborting"
                )
            page = self.get_historical_orders(limit=limit, cursor=cursor, ticker=ticker)
            if page.items:
                yield from page.items
            if not page.nextPagePath:
                return
            cursor = _cursor_from_next_page_path(page.nextPagePath)
            if cursor is None:
                return

    def iter_all_dividends(
        self,
        *,
        limit: int = _HISTORY_LIMIT_MAX,
        ticker: Optional[str] = None,
    ) -> Iterator[HistoryDividendItem]:
        """Yield every historical dividend, transparently following ``nextPagePath``."""
        cursor: Optional[str] = None
        pages = 0
        while True:
            pages += 1
            if pages > _MAX_PAGINATION_PAGES:
                raise RuntimeError(
                    f"iter_all_dividends exceeded {_MAX_PAGINATION_PAGES} pages; aborting"
                )
            page = self.get_historical_dividends(
                limit=limit, cursor=cursor, ticker=ticker
            )
            if page.items:
                yield from page.items
            if not page.nextPagePath:
                return
            cursor = _cursor_from_next_page_path(page.nextPagePath)
            if cursor is None:
                return

    def iter_all_transactions(
        self,
        *,
        limit: int = _HISTORY_LIMIT_MAX,
        time: Optional[str] = None,
    ) -> Iterator[HistoryTransactionItem]:
        """Yield every transaction, transparently following ``nextPagePath``."""
        cursor: Optional[str] = None
        pages = 0
        while True:
            pages += 1
            if pages > _MAX_PAGINATION_PAGES:
                raise RuntimeError(
                    f"iter_all_transactions exceeded {_MAX_PAGINATION_PAGES} pages; aborting"
                )
            page = self.get_historical_transactions(
                limit=limit, cursor=cursor, time=time
            )
            if page.items:
                yield from page.items
            if not page.nextPagePath:
                return
            cursor = _cursor_from_next_page_path(page.nextPagePath)
            if cursor is None:
                return

    # 2c. Report polling helper implementing the async workflow.
    def wait_for_report(
        self,
        report_id: int,
        *,
        timeout: float = 300.0,
        poll_interval: float = 10.0,
    ) -> ReportResponse:
        """Poll ``GET /equity/history/exports`` until ``report_id`` reaches a terminal state.

        Implements the asynchronous report workflow documented in the spec:
        ``POST /history/exports`` returns a ``reportId``, then the caller polls
        ``GET /history/exports`` until ``status == "Finished"`` (at which point
        ``downloadLink`` is populated). Other terminal statuses
        (``Canceled``, ``Failed``) raise ``RuntimeError``. Raises
        ``TimeoutError`` if no terminal state is reached within ``timeout``
        seconds.
        """
        deadline = time.monotonic() + timeout
        while True:
            reports = self.get_historical_exports()
            match = next((r for r in reports if r.reportId == report_id), None)
            if match is None:
                raise RuntimeError(
                    f"reportId {report_id} not found in GET /equity/history/exports"
                )
            status = match.status
            if status and status.value in {"Finished"}:
                return match
            if status and status.value in {"Canceled", "Failed"}:
                raise RuntimeError(
                    f"reportId {report_id} terminated with status {status.value}"
                )
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"reportId {report_id} not finished within {timeout:g}s"
                    f" (last status: {status.value if status else None})"
                )
            time.sleep(poll_interval)

    # 3. Metadata (Instruments)
    def get_exchanges(self) -> List[Exchange]:
        return [Exchange(**x) for x in self._get("/equity/metadata/exchanges").json()]

    def get_instruments(self) -> List[TradableInstrument]:
        return [
            TradableInstrument(**x)
            for x in self._get("/equity/metadata/instruments").json()
        ]

    def _ensure_instrument_cache(self) -> None:
        """Fetch and cache instruments for ticker<->ISIN lookups (single API call)."""
        if self._instruments_cache is not None:
            return
        instruments = self.get_instruments()
        self._instruments_cache = instruments
        self._ticker_to_isin = {
            i.ticker: i.isin for i in instruments if i.ticker and i.isin
        }
        self._isin_to_ticker = {
            i.isin: i.ticker for i in instruments if i.ticker and i.isin
        }

    def resolve_ticker_from_isin(self, isin: str) -> Optional[str]:
        """Resolve a single ISIN to its T212 ticker using cached instruments."""
        self._ensure_instrument_cache()
        if self._isin_to_ticker is None:
            return None
        return self._isin_to_ticker.get(isin)

    def resolve_isin_from_ticker(self, ticker: str) -> Optional[str]:
        """Resolve a single T212 ticker to its ISIN using cached instruments."""
        self._ensure_instrument_cache()
        if self._ticker_to_isin is None:
            return None
        return self._ticker_to_isin.get(ticker)

    def resolve_isins_from_tickers(self) -> dict[str, str]:
        """Return full ticker->ISIN mapping (cached, single API call)."""
        self._ensure_instrument_cache()
        if self._ticker_to_isin is None:
            return {}
        return dict(self._ticker_to_isin)

    # 4. Orders
    def get_orders(self) -> List[Order]:
        return [Order(**x) for x in self._get("/equity/orders").json()]

    def place_limit_order(self, request: LimitRequest) -> Order:
        return Order(
            **self._post(
                "/equity/orders/limit", request.model_dump(exclude_none=True)
            ).json()
        )

    def place_market_order(self, request: MarketRequest) -> Order:
        return Order(
            **self._post(
                "/equity/orders/market", request.model_dump(exclude_none=True)
            ).json()
        )

    def place_stop_order(self, request: StopRequest) -> Order:
        return Order(
            **self._post(
                "/equity/orders/stop", request.model_dump(exclude_none=True)
            ).json()
        )

    def place_stop_limit_order(self, request: StopLimitRequest) -> Order:
        return Order(
            **self._post(
                "/equity/orders/stop_limit", request.model_dump(exclude_none=True)
            ).json()
        )

    def cancel_order(self, order_id: int) -> None:
        self._delete(f"/equity/orders/{order_id}")

    def get_order_by_id(self, order_id: int) -> Order:
        return Order(**self._get(f"/equity/orders/{order_id}").json())

    # 5. Pies (Deprecated, but implementing per request)
    def get_pies(self) -> List[AccountBucketResultResponse]:
        return [
            AccountBucketResultResponse(**x) for x in self._get("/equity/pies").json()
        ]

    def create_pie(
        self, request: PieRequest
    ) -> AccountBucketInstrumentsDetailedResponse:
        return AccountBucketInstrumentsDetailedResponse(
            **self._post("/equity/pies", request.model_dump(exclude_none=True)).json()
        )

    def delete_pie(self, pie_id: int) -> None:
        self._delete(f"/equity/pies/{pie_id}")

    def get_pie_by_id(self, pie_id: int) -> AccountBucketInstrumentsDetailedResponse:
        return AccountBucketInstrumentsDetailedResponse(
            **self._get(f"/equity/pies/{pie_id}").json()
        )

    def update_pie(
        self, pie_id: int, request: PieRequest
    ) -> AccountBucketInstrumentsDetailedResponse:
        return AccountBucketInstrumentsDetailedResponse(
            **self._post(
                f"/equity/pies/{pie_id}", request.model_dump(exclude_none=True)
            ).json()
        )

    def duplicate_pie(
        self, pie_id: int, request: DuplicateBucketRequest
    ) -> AccountBucketInstrumentsDetailedResponse:
        return AccountBucketInstrumentsDetailedResponse(
            **self._post(
                f"/equity/pies/{pie_id}/duplicate",
                request.model_dump(exclude_none=True),
            ).json()
        )

    # 6. Positions
    def get_positions(self, ticker: Optional[str] = None) -> List[Position]:
        params = {}
        if ticker:
            params["ticker"] = ticker
        return [Position(**x) for x in self._get("/equity/positions", params).json()]
