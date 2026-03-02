import typer
import os
from rich.console import Console
from t212_cli.client.base import Trading212Client

app = typer.Typer(help="Trading 212 CLI")
console = Console()


def get_client() -> Trading212Client:
    api_key_id = os.environ.get("T212_API_KEY_ID")
    secret_key = os.environ.get("T212_SECRET_KEY")

    if not api_key_id or not secret_key:
        console.print(
            "[red]Error: Both T212_API_KEY_ID and T212_SECRET_KEY environment variables must be set.[/red]"
        )
        raise typer.Exit(code=1)

    return Trading212Client(api_key_id=api_key_id, secret_key=secret_key)


@app.command()
def account() -> None:
    """Get account information."""
    client = get_client()
    try:
        info = client.get_account_info()
        console.print(info.model_dump())
    except Exception as e:
        console.print(f"[red]Error fetching account: {e}[/red]")
