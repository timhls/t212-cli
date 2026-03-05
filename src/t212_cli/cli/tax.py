import typer
import os
import datetime
import urllib.parse
from rich.console import Console
from rich.table import Table
from t212_cli.tax.config import (
    get_instrument_config,
    update_instrument_config,
    load_tax_config,
)
from t212_cli.tax.scraper import scrape_finanzfluss
from t212_cli.client.base import Trading212Client
from t212_cli.tax.calculator import FifoEngine, TaxEvent
from t212_cli.models import Side, HistoricalOrder

app = typer.Typer(help="German Tax Reporting Commands (FiFo, TFS, Vorabpauschale)")
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


@app.command("config")
def show_config() -> None:
    """Show the current local tax configuration for instruments."""
    config = load_tax_config()
    if not config.instruments:
        console.print("[yellow]No tax configurations saved yet.[/yellow]")
        return

    for isin, instr in config.instruments.items():
        console.print(
            f"[bold cyan]{isin}[/bold cyan]: {instr.model_dump_json(indent=2)}"
        )


@app.command("classify")
def classify_instrument(isin: str) -> None:
    """Auto-detect the tax classification of an ISIN via scraping."""
    existing = get_instrument_config(isin)
    if existing:
        console.print(
            f"[green]Instrument {isin} is already configured locally:[/green]"
        )
        console.print(existing.model_dump_json(indent=2))
        return

    console.print(f"Scraping Finanzfluss for [bold yellow]{isin}[/bold yellow]...")
    instrument = scrape_finanzfluss(isin)

    if instrument:
        console.print(f"[green]Successfully detected tax profile for {isin}:[/green]")
        console.print(instrument.model_dump_json(indent=2))
        update_instrument_config(isin, instrument)
        console.print("[blue]Saved to ~/.t212/tax_config.yml[/blue]")
    else:
        console.print(
            f"[red]Could not auto-detect {isin}. Please configure manually.[/red]"
        )


@app.command("fifo-report")
def generate_fifo_report(year: int = 2024) -> None:
    """Generate a FiFo tax report for a specific tax year."""
    console.print(f"[bold green]Generating Tax Report for {year}...[/bold green]")

    client = get_client()

    console.print(
        "[dim]- Loading historical transactions from Trading 212 API...[/dim]"
    )

    # Fetch all historical orders using pagination
    all_orders: list[HistoricalOrder] = []
    cursor = None
    with console.status("[dim]Fetching orders...[/dim]"):
        while True:
            res = client.get_historical_orders(limit=50, cursor=cursor)
            if res.items:
                all_orders.extend(res.items)

            if not res.nextPagePath:
                break

            # next page path usually has cursor as a query param.
            # The API might just return the cursor string, let's parse it or assume cursor is just pagination offset
            # T212 API returns a string like "/api/v0/equity/history/orders?cursor=xxxx"
            # Let's extract the cursor from nextPagePath
            try:
                parsed_url = urllib.parse.urlparse(res.nextPagePath)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                cursor_str = query_params.get("cursor", [None])[0]
                if not cursor_str:
                    break
                cursor = int(cursor_str)
            except Exception:
                break

    console.print(f"[green]Loaded {len(all_orders)} historical orders.[/green]")

    def get_order_date(x: HistoricalOrder) -> datetime.datetime:
        if x.fill and x.fill.filledAt:
            return x.fill.filledAt
        if x.order and x.order.createdAt:
            return x.order.createdAt
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

    # Sort orders chronologically by execution time (fill.filledAt or order.createdAt)
    all_orders.sort(key=get_order_date)

    # Need a cache for missing ISINs to prevent repeated fetching
    missing_isins = set()

    events: list[TaxEvent] = []

    with console.status("[dim]Building Tax Events & Classifying Instruments...[/dim]"):
        for hist_order in all_orders:
            order = hist_order.order
            fill = hist_order.fill

            if (
                not order
                or not fill
                or not order.instrument
                or not order.instrument.isin
                or not fill.filledAt
                or not order.side
            ):
                continue

            isin = order.instrument.isin

            # Auto-classify if not configured
            if isin not in missing_isins and not get_instrument_config(isin):
                instrument = scrape_finanzfluss(isin)
                if instrument:
                    update_instrument_config(isin, instrument)
                else:
                    missing_isins.add(isin)

            # Extract fees from walletImpact (in EUR)
            fees_eur = 0.0
            if fill.walletImpact and fill.walletImpact.taxes:
                for tax in fill.walletImpact.taxes:
                    fees_eur += tax.quantity or 0.0

            # Extract FX rate if applicable
            fx_rate = 1.0
            if fill.walletImpact and fill.walletImpact.fxRate:
                fx_rate = fill.walletImpact.fxRate

            # Price in EUR (assuming account currency is EUR for now)
            # if filled value is provided, we can use it.
            price_eur = (fill.price or 0.0) / fx_rate

            events.append(
                TaxEvent(
                    date=fill.filledAt,
                    type="BUY" if order.side == Side.BUY else "SELL",
                    isin=isin,
                    quantity=fill.quantity or 0.0,
                    price_eur=price_eur,
                    fees_eur=fees_eur,
                )
            )

    console.print("[dim]- Executing FiFo matching...[/dim]")
    engine = FifoEngine(target_year=year)
    for event in events:
        engine.process_event(event)

    console.print("[dim]- Calculating Loss Buckets...[/dim]")

    # Print report
    console.print(f"\n[bold underline]Tax Report {year}[/bold underline]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan")
    table.add_column("Amount (EUR)", justify="right")

    table.add_row(
        "Total Taxable Capital Gains (Net)", f"{engine.year_taxable_gains:.2f} €"
    )
    table.add_row(
        "Stock Losses Generated (Aktien)",
        f"{engine.year_aktien_verlust_generated:.2f} €",
    )
    table.add_row(
        "Other Losses Generated (Sonstige)",
        f"{engine.year_sonstige_verlust_generated:.2f} €",
    )
    table.add_row("", "")
    table.add_row(
        "Current Global Stock Loss Bucket", f"{engine.aktien_verlusttopf:.2f} €"
    )
    table.add_row(
        "Current Global Other Loss Bucket", f"{engine.sonstige_verlusttopf:.2f} €"
    )

    console.print(table)
    console.print(
        "\n[dim]Note: This report assumes account base currency is EUR and does not yet include Dividends, Vorabpauschale, or daily interest payouts (Interest on Cash).[/dim]"
    )
