import httpx
import base64
from t212_cli.models import AccountSummary


class Trading212Client:
    BASE_URL = "https://live.trading212.com/api/v0"

    def __init__(self, api_key_id: str, secret_key: str):
        self.api_key_id = api_key_id
        self.secret_key = secret_key

        credentials_string = f"{api_key_id}:{secret_key}"
        encoded_credentials = base64.b64encode(
            credentials_string.encode("utf-8")
        ).decode("utf-8")

        self.headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Accept": "application/json",
        }

    def get_account_info(self) -> AccountSummary:
        response = httpx.get(
            f"{self.BASE_URL}/equity/account/info", headers=self.headers
        )
        response.raise_for_status()
        return AccountSummary(**response.json())
