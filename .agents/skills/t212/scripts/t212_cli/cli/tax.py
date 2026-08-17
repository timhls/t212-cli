import datetime
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from t212_cli.client.base import Trading212Client
from t212_cli.models import HistoricalOrder, Side
from t212_cli.tax.calculator import FifoEngine, TaxEvent
from t212_cli.tax.config import (
    get_instrument_config,
    load_tax_config,
    update_instrument_config,
)
from t212_cli.tax.csv_report import generate_csv_tax_report
from t212_cli.tax.scraper import scrape_finanzfluss

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

    # Fetch all historical orders using auto-pagination helper.
    # The spec's cursor-based nextPagePath workflow is handled inside the client.
    with console.status("[dim]Fetching orders...[/dim]"):
        all_orders = list(client.iter_all_orders())

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

    if engine.uncovered_sells:
        console.print(
            f"\n[bold red]WARNING:[/bold red] {len(engine.uncovered_sells)} "
            "instrument(s) with sells not covered by API orders:"
        )
        for isin, qty in engine.uncovered_sells.items():
            console.print(f"  [red]- {isin}: {qty:.6f} shares unmatched[/red]")
        console.print(
            "[yellow]The T212 API does not return 'Transfer in' (securities "
            "transfers) as rated fills. Use the official CSV export with "
            "'t212 tax csv-report' for correct results.[/yellow]"
        )

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


@app.command("csv-report")
def csv_report(
    path: Path = typer.Argument(
        ..., exists=True, dir_okay=False, help="Official T212 CSV export"
    ),
    year: int = typer.Argument(..., help="Tax year"),
    basiszins: Optional[float] = typer.Option(
        None, help="Basiszins override (default: 2023-2025 built-in)"
    ),
    show_inventory: bool = typer.Option(
        False, "--inventory", help="Show year-end holdings table"
    ),
) -> None:
    """German tax report from an official CSV export (covers Transfer-in)."""
    try:
        report = generate_csv_tax_report(path, year, basiszins=basiszins)
    except (ValueError, OSError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    console.print(f"\n[bold underline]CSV Tax Report {year}[/bold underline]")
    console.print(
        f"[dim]Source: {path.name} · Basiszins: {report.basiszins:.2%}[/dim]\n"
    )

    summary = Table(show_header=True, header_style="bold magenta")
    summary.add_column("Category", style="cyan")
    summary.add_column("Amount (EUR)", justify="right")
    interest = report.cash_sums.get("Interest on cash", 0.0) + report.cash_sums.get(
        "Lending interest", 0.0
    )
    summary.add_row(
        "Realized gains §20 (net, incl. TFS)", f"{report.fifo_taxable_gains:.2f} €"
    )
    summary.add_row("  of which Aktiengewinne/verluste (see below)", "")
    summary.add_row("Vorabpauschale (taxable)", f"{report.vorab_taxable_total:.2f} €")
    summary.add_row("Interest on cash + lending", f"{interest:.2f} €")
    summary.add_row(
        "[bold]Total §20 taxable (year)[/bold]",
        f"[bold]{report.year_taxable_gains_with_vorab:.2f} €[/bold]",
    )
    summary.add_row(
        "§23 gains (ETCs, check 1.000 € Freigrenze)", f"{report.sec23_gains:.2f} €"
    )
    summary.add_row("Aktien losses generated", f"{report.aktien_verluste:.2f} €")
    summary.add_row("Sonstige losses generated", f"{report.sonstige_verluste:.2f} €")
    if report.cash_sums.get("Spending cashback"):
        summary.add_row(
            "Spending cashback (document only)",
            f"{report.cash_sums['Spending cashback']:.2f} €",
        )
    console.print(summary)

    if report.sells:
        console.print("\n[bold]Sells[/bold]")
        sells_table = Table(show_header=True, header_style="bold magenta")
        sells_table.add_column("Date")
        sells_table.add_column("Ticker")
        sells_table.add_column("Qty", justify="right")
        sells_table.add_column("Proceeds €", justify="right")
        sells_table.add_column("T212 Result €", justify="right")
        sells_table.add_column("Class")
        for s in report.sells:
            sells_table.add_row(
                s.date.date().isoformat(),
                s.ticker,
                f"{s.quantity:.6f}",
                f"{s.net_proceeds_eur:.2f}",
                f"{s.t212_result_eur:.2f}",
                s.asset_class,
            )
        console.print(sells_table)

    if report.vorab_rows:
        console.print("\n[bold]Vorabpauschale[/bold]")
        vorab_table = Table(show_header=True, header_style="bold magenta")
        vorab_table.add_column("ISIN")
        vorab_table.add_column("Qty", justify="right")
        vorab_table.add_column("Gross €", justify="right")
        vorab_table.add_column("TFS", justify="right")
        vorab_table.add_column("Taxable €", justify="right")
        for v in report.vorab_rows:
            vorab_table.add_row(
                v.isin,
                f"{v.quantity:.4f}",
                f"{v.gross:.2f}",
                f"{v.tfs_quote:.0%}",
                f"{v.taxable:.2f}",
            )
        console.print(vorab_table)

    if show_inventory and report.inventory:
        console.print("\n[bold]Inventory (year end)[/bold]")
        inv_table = Table(show_header=True, header_style="bold magenta")
        inv_table.add_column("ISIN")
        inv_table.add_column("Name")
        inv_table.add_column("Qty", justify="right")
        inv_table.add_column("Cost €", justify="right")
        for i in report.inventory:
            inv_table.add_row(
                i.isin, i.name[:40], f"{i.quantity:.6f}", f"{i.cost_eur:.2f}"
            )
        console.print(inv_table)

    if report.warnings:
        console.print("\n[bold yellow]Warnings[/bold yellow]")
        for w in report.warnings:
            console.print(f"[yellow]- {w}[/yellow]")
