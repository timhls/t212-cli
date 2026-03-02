from typing import Any, Optional
import typer
import os
import json
from rich.console import Console
from t212_cli.client.base import Trading212Client
from t212_cli.models import MarketRequest

app = typer.Typer(help="Trading 212 CLI")
console = Console()

account_app = typer.Typer(help="Account summary and commands")
history_app = typer.Typer(
    help="Historical events (dividends, exports, orders, transactions)"
)
metadata_app = typer.Typer(help="Instruments and exchanges")
orders_app = typer.Typer(help="Place, modify, or list orders")
pies_app = typer.Typer(help="Manage investment pies")
positions_app = typer.Typer(help="Manage open positions")

app.add_typer(account_app, name="account")
app.add_typer(history_app, name="history")
app.add_typer(metadata_app, name="metadata")
app.add_typer(orders_app, name="orders")
app.add_typer(pies_app, name="pies")
app.add_typer(positions_app, name="positions")


def get_client() -> Trading212Client:
    api_key_id = os.environ.get("T212_API_KEY_ID")
    secret_key = os.environ.get("T212_SECRET_KEY")

    if not api_key_id or not secret_key:
        console.print(
            "[red]Error: Both T212_API_KEY_ID and T212_SECRET_KEY environment variables must be set.[/red]"
        )
        raise typer.Exit(code=1)

    return Trading212Client(api_key_id=api_key_id, secret_key=secret_key)


def pretty_print(model: Any) -> None:
    if isinstance(model, list):
        console.print_json(
            json.dumps([m.model_dump(exclude_none=True) for m in model], default=str)
        )
    else:
        console.print_json(model.model_dump_json(exclude_none=True))


# === ACCOUNT ===
@account_app.command("summary")
def account_summary() -> None:
    """Get account summary."""
    client = get_client()
    try:
        info = client.get_account_summary()
        pretty_print(info)
    except Exception as e:
        console.print(f"[red]Error fetching account summary: {e}[/red]")


# === POSITIONS ===
@positions_app.command("list")
def positions_list(ticker: str = typer.Option(None, help="Filter by ticker")) -> None:
    """List all open positions."""
    client = get_client()
    try:
        positions = client.get_positions(ticker=ticker)
        pretty_print(positions)
    except Exception as e:
        console.print(f"[red]Error fetching positions: {e}[/red]")


# === HISTORY ===
@history_app.command("dividends")
def history_dividends(
    limit: int = 20, cursor: Optional[int] = None, ticker: Optional[str] = None
) -> None:
    """Get historical dividends."""
    client = get_client()
    try:
        res = client.get_historical_dividends(limit, cursor, ticker)
        pretty_print(res)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@history_app.command("orders")
def history_orders(
    limit: int = 20, cursor: Optional[int] = None, ticker: Optional[str] = None
) -> None:
    """Get historical orders."""
    client = get_client()
    try:
        res = client.get_historical_orders(limit, cursor, ticker)
        pretty_print(res)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@history_app.command("transactions")
def history_transactions(
    limit: int = 20, cursor: Optional[str] = None, time: Optional[str] = None
) -> None:
    """Get historical transactions."""
    client = get_client()
    try:
        res = client.get_historical_transactions(limit, cursor, time)
        pretty_print(res)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


# === METADATA ===
@metadata_app.command("exchanges")
def metadata_exchanges() -> None:
    """Get all exchanges."""
    client = get_client()
    try:
        pretty_print(client.get_exchanges())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@metadata_app.command("instruments")
def metadata_instruments() -> None:
    """Get all instruments."""
    client = get_client()
    try:
        pretty_print(client.get_instruments())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


# === ORDERS ===
@orders_app.command("list")
def orders_list() -> None:
    """List pending orders."""
    client = get_client()
    try:
        pretty_print(client.get_orders())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@orders_app.command("get")
def orders_get(order_id: int) -> None:
    """Get an order by ID."""
    client = get_client()
    try:
        pretty_print(client.get_order_by_id(order_id))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@orders_app.command("cancel")
def orders_cancel(order_id: int) -> None:
    """Cancel an order by ID."""
    client = get_client()
    try:
        client.cancel_order(order_id)
        console.print(f"[green]Order {order_id} cancelled.[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@orders_app.command("market")
def orders_market(ticker: str, quantity: float, extended_hours: bool = False) -> None:
    """Place a market order."""
    client = get_client()
    try:
        req = MarketRequest(
            ticker=ticker, quantity=quantity, extendedHours=extended_hours
        )
        res = client.place_market_order(req)
        pretty_print(res)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
