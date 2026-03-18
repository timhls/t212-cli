import httpx
import base64
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

    def __init__(self, api_key_id: str, secret_key: str, base_url: str = DEMO_URL):
        self.api_key_id = api_key_id
        self.secret_key = secret_key
        self.base_url = base_url

        credentials_string = f"{api_key_id}:{secret_key}"
        encoded_credentials = base64.b64encode(
            credentials_string.encode("utf-8")
        ).decode("utf-8")

        self.headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Accept": "application/json",
        }

    def _get(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        response = httpx.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response

    def _post(
        self, endpoint: str, json_data: Optional[dict[str, Any]] = None
    ) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        response = httpx.post(url, headers=self.headers, json=json_data)
        response.raise_for_status()
        return response

    def _delete(self, endpoint: str) -> httpx.Response:
        url = f"{self.base_url}{endpoint}"
        response = httpx.delete(url, headers=self.headers)
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
        cursor: Optional[int] = None,
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
