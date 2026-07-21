from typing import Any, Optional
from datetime import datetime
import typer
import os
import json
from rich.console import Console
from t212_cli.client.base import Trading212Client
from t212_cli.models import (
    MarketRequest,
    LimitRequest,
    StopRequest,
    StopLimitRequest,
    TimeValidity,
    PublicReportRequest,
    ReportDataIncluded,
    PieRequest,
    DuplicateBucketRequest,
)
from t212_cli.cli.tax import app as tax_app
from t212_cli.tax.charts import (
    SummaryRow,
    fmt_date_range,
    render_line_chart,
    render_summary_table,
)
from t212_cli.tax.history import fetch_pie_history, summary_stats
from t212_cli.tax.justetf import scrape_justetf, enrich_profile_with_yahoo
from t212_cli.tax.pie_analysis import analyze_pie

app = typer.Typer(help="Trading 212 CLI")
console = Console()


account_app = typer.Typer(help="Account summary and commands")
etf_app = typer.Typer(help="ETF profile, holdings, regions, and sectors")
history_app = typer.Typer(
    help="Historical events (dividends, exports, orders, transactions)"
)
metadata_app = typer.Typer(help="Instruments and exchanges")
orders_app = typer.Typer(help="Place, modify, or list orders")
pies_app = typer.Typer(help="Manage investment pies")
positions_app = typer.Typer(help="Manage open positions")

app.add_typer(account_app, name="account")
app.add_typer(etf_app, name="etf")
app.add_typer(history_app, name="history")
app.add_typer(metadata_app, name="metadata")
app.add_typer(orders_app, name="orders")
app.add_typer(pies_app, name="pies")
app.add_typer(positions_app, name="positions")
app.add_typer(tax_app, name="tax")


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
    limit: int = 20, cursor: Optional[str] = None, ticker: Optional[str] = None
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
    limit: int = 20, cursor: Optional[str] = None, ticker: Optional[str] = None
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


history_exports_app = typer.Typer(help="Manage asynchronous CSV reports")
history_app.add_typer(history_exports_app, name="exports")


@history_exports_app.command("list")
def history_exports_list() -> None:
    """List all generated reports and their status."""
    client = get_client()
    try:
        pretty_print(client.get_historical_exports())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@history_exports_app.command("request")
def history_exports_request(
    time_from: str,
    time_to: str,
    include_orders: bool = True,
    include_dividends: bool = True,
    include_transactions: bool = True,
    include_interest: bool = False,
    wait: bool = False,
    poll_timeout: float = 300.0,
) -> None:
    """Request a CSV report (asynchronous). Pass --wait to block until Finished."""
    client = get_client()
    try:
        req = PublicReportRequest(
            timeFrom=datetime.fromisoformat(time_from),
            timeTo=datetime.fromisoformat(time_to),
            dataIncluded=ReportDataIncluded(
                includeOrders=include_orders,
                includeDividends=include_dividends,
                includeTransactions=include_transactions,
                includeInterest=include_interest,
            ),
        )
        enqueued = client.request_historical_export(req)
        console.print(f"[green]Report enqueued: reportId={enqueued.reportId}[/green]")
        if wait:
            console.print(
                f"[dim]Polling until Finished (timeout {poll_timeout:g}s)...[/dim]"
            )
            finished = client.wait_for_report(
                enqueued.reportId or 0, timeout=poll_timeout
            )
            pretty_print(finished)
            if finished.downloadLink:
                console.print(
                    f"[bold green]Download:[/bold green] {finished.downloadLink}"
                )
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
    """Place a market order (positive quantity = buy, negative = sell)."""
    client = get_client()
    try:
        req = MarketRequest(
            ticker=ticker, quantity=quantity, extendedHours=extended_hours
        )
        res = client.place_market_order(req)
        pretty_print(res)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@orders_app.command("limit")
def orders_limit(
    ticker: str,
    quantity: float,
    limit_price: float,
    time_validity: TimeValidity = TimeValidity.DAY,
) -> None:
    """Place a limit order (positive quantity = buy, negative = sell)."""
    client = get_client()
    try:
        req = LimitRequest(
            ticker=ticker,
            quantity=quantity,
            limitPrice=limit_price,
            timeValidity=time_validity,
        )
        res = client.place_limit_order(req)
        pretty_print(res)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@orders_app.command("stop")
def orders_stop(
    ticker: str,
    quantity: float,
    stop_price: float,
    time_validity: TimeValidity = TimeValidity.DAY,
) -> None:
    """Place a stop order (positive quantity = buy, negative = sell / stop-loss)."""
    client = get_client()
    try:
        req = StopRequest(
            ticker=ticker,
            quantity=quantity,
            stopPrice=stop_price,
            timeValidity=time_validity,
        )
        res = client.place_stop_order(req)
        pretty_print(res)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@orders_app.command("stop-limit")
def orders_stop_limit(
    ticker: str,
    quantity: float,
    stop_price: float,
    limit_price: float,
    time_validity: TimeValidity = TimeValidity.DAY,
) -> None:
    """Place a stop-limit order (positive quantity = buy, negative = sell)."""
    client = get_client()
    try:
        req = StopLimitRequest(
            ticker=ticker,
            quantity=quantity,
            stopPrice=stop_price,
            limitPrice=limit_price,
            timeValidity=time_validity,
        )
        res = client.place_stop_limit_order(req)
        pretty_print(res)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


# === PIES ===
@pies_app.command("list")
def pies_list() -> None:
    """Fetch all pies."""
    client = get_client()
    try:
        pretty_print(client.get_pies())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@pies_app.command("get")
def pies_get(pie_id: int) -> None:
    """Fetch a pie by ID."""
    client = get_client()
    try:
        pretty_print(client.get_pie_by_id(pie_id))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@pies_app.command("components")
def pies_components(pie_id: int) -> None:
    """List the instruments (components) of a pie by ID."""
    client = get_client()
    try:
        detail = client.get_pie_by_id(pie_id)
        instruments = detail.instruments or []
        if not instruments:
            console.print(f"[yellow]Pie {pie_id} has no components.[/yellow]")
            return
        pretty_print(instruments)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@pies_app.command("analyze")
def pies_analyze(
    pie_id: int,
    top: int = typer.Option(30, "--top", help="Number of top holdings to show"),
    no_yahoo: bool = typer.Option(
        False, "--no-yahoo", help="Skip Yahoo Finance enrichment"
    ),
) -> None:
    """Deep-dive analysis of a pie: aggregated holdings, regions, and sectors.

    Fetches underlying ETF holdings via justETF, weights each by the
    component's current pie share, and aggregates across all ETFs.
    Outputs JSON with top holdings, geographic breakdown, and sector breakdown.
    """
    client = get_client()
    try:
        result = analyze_pie(client, pie_id, enrich_with_yahoo=not no_yahoo)
        data = result.to_dict()
        if top > 0:
            data["top_holdings"] = data["top_holdings"][:top]
        console.print_json(json.dumps(data, default=str))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@pies_app.command("history")
def pies_history(
    pie_id: int,
    days: int = typer.Option(
        30, "--days", "-d", help="Number of calendar days of history"
    ),
    currency: str = typer.Option(
        "EUR", "--currency", "-c", help="Target currency for all values"
    ),
    height: int = typer.Option(
        16, "--height", help="Chart height in rows (aggregate chart)"
    ),
    per_component: bool = typer.Option(
        True,
        "--per-component/--no-per-component",
        help="Also render a chart per individual component",
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Output raw JSON instead of charts"
    ),
) -> None:
    """Reconstruct daily value history for a pie.

    Fetches the current pie composition, resolves each component ISIN to a
    Yahoo Finance symbol, and pulls daily close prices for the requested
    window. Values are FX-normalized to the target currency and multiplied
    by the current owned quantity per component.

    Caveats:
    - Quantities are assumed constant across the window (T212 API exposes
      only current holdings, not historical snapshots).
    - Price return only — dividends not included.
    """
    client = get_client()
    try:
        pie = fetch_pie_history(client, pie_id, days=days, target_currency=currency)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    if not pie.components:
        console.print(
            f"[yellow]No components with price data found for pie {pie_id}.[/yellow]"
        )
        return

    if json_out:
        payload = {
            "pie_id": pie.pie_id,
            "pie_name": pie.pie_name,
            "currency": pie.target_currency,
            "cash": pie.cash,
            "date_range": {
                "start": pie.start_date.isoformat(),
                "end": pie.end_date.isoformat(),
            },
            "aggregate": [
                {"date": d.isoformat(), "value": float(v)}
                for d, v in pie.aggregate_value.items()
            ],
            "components": [
                {
                    "ticker": c.ticker,
                    "isin": c.isin,
                    "yahoo_symbol": c.yahoo_symbol,
                    "quantity": c.quantity,
                    "fund_currency": c.fund_currency,
                    "series": [
                        {"date": d.isoformat(), "value": float(v)}
                        for d, v in c.value_history.items()
                    ],
                }
                for c in pie.components
            ],
        }
        console.print_json(json.dumps(payload, default=str))
        return

    # === Header ===
    console.rule(
        f"[bold cyan]Pie '{pie.pie_name}' ({pie.pie_id}) — "
        f"{days}-day value history[/bold cyan]"
    )
    console.print(
        f"[dim]Range: {fmt_date_range(pie.start_date, pie.end_date)}  "
        f"·  Currency: {currency}  ·  Cash: {pie.cash:,.2f} {currency}[/dim]"
    )
    console.print(
        "[dim]Assumes constant quantities; price return only (no dividends).[/dim]"
    )
    console.print()

    # === Aggregate chart ===
    agg_stats = summary_stats(pie.aggregate_value)
    color = "green" if agg_stats.get("pct_change", 0.0) >= 0 else "red"
    console.print(
        f"[bold]Aggregate pie value[/bold]  "
        f"{agg_stats.get('start_value', 0):,.2f} → "
        f"{agg_stats.get('end_value', 0):,.2f} {currency}  "
        f"[{color}]{agg_stats.get('pct_change', 0):+.2f}%[/{color}]  "
        f"[dim]min {agg_stats.get('min_value', 0):,.2f} · "
        f"max {agg_stats.get('max_value', 0):,.2f} · "
        f"vol {agg_stats.get('volatility_pct', 0):.1f}%[/dim]"
    )
    console.print()
    render_line_chart(
        pie.aggregate_value,
        title=f"Total pie value ({currency})",
        currency=currency,
        height=height,
        color=color,
        console=console,
    )
    console.print()

    # === Per-component summary + charts ===
    rows: list[SummaryRow] = []
    for c in pie.components:
        stats = summary_stats(c.value_history)
        rows.append(
            {
                "ticker": c.ticker,
                "symbol": c.yahoo_symbol,
                "name": c.isin,
                "start_value": float(stats.get("start_value", 0.0)),
                "end_value": float(stats.get("end_value", 0.0)),
                "pct_change": float(stats.get("pct_change", 0.0)),
                "values": list(c.value_history.to_numpy()),
            }
        )

    render_summary_table(rows, currency=currency, console=console)
    console.print()

    if per_component:
        console.rule("[bold cyan]Per-component value charts[/bold cyan]")
        console.print()
        for c in pie.components:
            stats = summary_stats(c.value_history)
            pct = stats.get("pct_change", 0.0)
            cc = "green" if pct >= 0 else "red"
            console.print(
                f"[bold]{c.ticker}[/bold]  [dim]{c.yahoo_symbol}[/dim]  "
                f"{c.isin}  ·  qty {c.quantity:.4f}  ·  "
                f"[{cc}]{pct:+.2f}%[/{cc}]"
            )
            render_line_chart(
                c.value_history,
                currency=currency,
                height=8,
                color=cc,
                console=console,
            )
            console.print()


@pies_app.command("delete")
def pies_delete(pie_id: int) -> None:
    """Delete a pie by ID."""
    client = get_client()
    try:
        client.delete_pie(pie_id)
        console.print(f"[green]Pie {pie_id} deleted.[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@pies_app.command("create")
def pies_create(
    payload: str = typer.Argument(
        ..., help='JSON string or path to JSON file. Example: {"name": "Tech"}'
    ),
) -> None:
    """Create a new pie from a JSON payload.

    The payload must match the PieRequest schema.
    Example JSON:
    {
      "dividendCashAction": "REINVEST",
      "endDate": "2025-12-31T23:59:59Z",
      "goal": 10000.0,
      "icon": "Default",
      "instrumentShares": {
        "AAPL_US_EQ": 0.5,
        "MSFT_US_EQ": 0.5
      },
      "name": "My Tech Pie"
    }
    """
    client = get_client()
    try:
        if os.path.exists(payload):
            with open(payload, "r") as f:
                data = json.load(f)
        else:
            data = json.loads(payload)

        req = PieRequest(**data)
        pretty_print(client.create_pie(req))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@pies_app.command("update")
def pies_update(
    pie_id: int,
    payload: str = typer.Argument(
        ..., help='JSON string or path to JSON file. Example: {"name": "Tech"}'
    ),
) -> None:
    """Update an existing pie by ID using a JSON payload.

    The payload must match the PieRequest schema.
    Example JSON:
    {
      "dividendCashAction": "REINVEST",
      "goal": 15000.0,
      "icon": "Default",
      "instrumentShares": {
        "AAPL_US_EQ": 0.6,
        "MSFT_US_EQ": 0.4
      },
      "name": "My Updated Tech Pie"
    }
    """
    client = get_client()
    try:
        if os.path.exists(payload):
            with open(payload, "r") as f:
                data = json.load(f)
        else:
            data = json.loads(payload)

        req = PieRequest(**data)
        pretty_print(client.update_pie(pie_id, req))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@pies_app.command("duplicate")
def pies_duplicate(
    pie_id: int,
    payload: str = typer.Argument(
        ..., help='JSON string or path to JSON file. Example: {"name": "Tech Copy"}'
    ),
) -> None:
    """Duplicate an existing pie by ID using a JSON payload.

    The payload must match the DuplicateBucketRequest schema.
    Example JSON:
    {
      "icon": "Default",
      "name": "Copy of Tech Pie"
    }
    """
    client = get_client()
    try:
        if os.path.exists(payload):
            with open(payload, "r") as f:
                data = json.load(f)
        else:
            data = json.loads(payload)

        req = DuplicateBucketRequest(**data)
        pretty_print(client.duplicate_pie(pie_id, req))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def _resolve_ticker_from_isin(isin: str) -> str | None:
    client = get_client()
    try:
        return client.resolve_ticker_from_isin(isin)
    except Exception:  # noqa: B110  # nosec B110
        pass
    return None


def _enrich_with_yahoo(profile: Any, isin: str) -> Any:
    ticker = _resolve_ticker_from_isin(isin)
    if not ticker:
        return profile
    return enrich_profile_with_yahoo(profile, ticker)


# === ETF ===
@etf_app.command("profile")
def etf_profile(isin: str) -> None:
    """Get full ETF profile (holdings, regions, sectors, TER, etc.)."""
    try:
        profile = scrape_justetf(isin)
        if not profile:
            console.print(f"[red]Could not fetch ETF profile for ISIN {isin}.[/red]")
            return
        profile = _enrich_with_yahoo(profile, isin)
        if not profile.asset_classes and not profile.holdings and not profile.countries:
            console.print(
                f"[yellow]No detailed data found for ISIN {isin}. "
                "This may not be a UCITS ETF or justETF may not cover it.[/yellow]"
            )
        pretty_print(profile)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@etf_app.command("holdings")
def etf_holdings(isin: str) -> None:
    """Get ETF top holdings."""
    try:
        profile = scrape_justetf(isin)
        if not profile or not profile.holdings:
            ticker = _resolve_ticker_from_isin(isin)
            if not ticker:
                console.print(f"[red]No holdings found for ISIN {isin}.[/red]")
                return
            from t212_cli.tax.models import EtfProfile

            profile = enrich_profile_with_yahoo(EtfProfile(isin=isin), ticker)
            if profile.holdings:
                pretty_print(profile.holdings)
                return
            console.print(f"[red]No holdings found for ISIN {isin}.[/red]")
            return
        pretty_print(profile.holdings)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@etf_app.command("regions")
def etf_regions(isin: str) -> None:
    """Get ETF geographic region breakdown."""
    try:
        profile = scrape_justetf(isin)
        if not profile or not profile.countries:
            console.print(f"[red]No country/region data found for ISIN {isin}.[/red]")
            return
        import json

        console.print_json(json.dumps(profile.countries, default=str))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@etf_app.command("sectors")
def etf_sectors(isin: str) -> None:
    """Get ETF sector breakdown."""
    try:
        profile = scrape_justetf(isin)
        if not profile or not profile.sectors:
            ticker = _resolve_ticker_from_isin(isin)
            if not ticker:
                console.print(f"[red]No sector data found for ISIN {isin}.[/red]")
                return
            from t212_cli.tax.models import EtfProfile

            profile = enrich_profile_with_yahoo(EtfProfile(isin=isin), ticker)
            if profile.sectors:
                console.print_json(json.dumps(profile.sectors, default=str))
                return
            console.print(f"[red]No sector data found for ISIN {isin}.[/red]")
            return
        console.print_json(json.dumps(profile.sectors, default=str))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
