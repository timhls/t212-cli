import httpx
from t212_cli.models import AccountSummary


class Trading212Client:
    BASE_URL = "https://live.trading212.com/api/v0"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"Authorization": self.api_key}

    def get_account_info(self) -> AccountSummary:
        response = httpx.get(
            f"{self.BASE_URL}/equity/account/info", headers=self.headers
        )
        response.raise_for_status()
        return AccountSummary(**response.json())
