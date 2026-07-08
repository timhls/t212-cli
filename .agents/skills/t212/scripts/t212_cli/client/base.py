import httpx
import base64
import os
from typing import Optional, List, Any
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
)


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

    def _get(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        response = self.client.get(url, params=params)
        response.raise_for_status()
        return response

    def _post(
        self, endpoint: str, json_data: Optional[dict[str, Any]] = None
    ) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        response = self.client.post(url, json=json_data)
        response.raise_for_status()
        return response

    def _delete(self, endpoint: str) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        response = self.client.delete(url)
        response.raise_for_status()
        return response

    # 1. Accounts
    def get_account_summary(self) -> AccountSummary:
        response = self._get("/equity/account/summary")
        return AccountSummary(**response.json())

    # 2. Historical events
    def get_historical_dividends(
        self,
        limit: int = 20,
        cursor: Optional[int] = None,
        ticker: Optional[str] = None,
    ) -> PaginatedResponseHistoryDividendItem:
        params: dict[str, Any] = {"limit": limit}
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
        cursor: Optional[int | str] = None,
        ticker: Optional[str] = None,
    ) -> PaginatedResponseHistoricalOrder:
        params: dict[str, Any] = {"limit": limit}
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
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if time:
            params["time"] = time
        return PaginatedResponseHistoryTransactionItem(
            **self._get("/equity/history/transactions", params).json()
        )

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
