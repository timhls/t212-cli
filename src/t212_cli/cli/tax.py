import typer
from rich.console import Console
from t212_cli.tax.config import (
    get_instrument_config,
    update_instrument_config,
    load_tax_config,
)
from t212_cli.tax.scraper import scrape_finanzfluss

app = typer.Typer(help="German Tax Reporting Commands (FiFo, TFS, Vorabpauschale)")
console = Console()


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
    """Generate a FiFo tax report for a specific tax year. (Stub)"""
    console.print(f"[bold green]Generating Tax Report for {year}...[/bold green]")
    console.print(
        "[dim]- Loading historical transactions from Trading 212 API...[/dim]"
    )
    console.print("[dim]- Resolving Tax Classifications (ETFs/ETCs)...[/dim]")
    console.print("[dim]- Executing FiFo matching...[/dim]")
    console.print("[dim]- Calculating Loss Buckets...[/dim]")
    console.print(
        "[bold yellow]This feature is currently under active development. Scaffold complete.[/bold yellow]"
    )
