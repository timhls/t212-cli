"""212 Card transaction commands.

Backed by Trading 212's *private* cards web API (cookie-authenticated), not
the public API — see :mod:`t212_cli.client.cards`.
"""

import json
from datetime import datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import typer
from rich.console import Console
from t212_cli.card_report import render_csv, render_markdown
from t212_cli.client.cards import (
    CardsClient,
    CardSessionExpiredError,
    resolve_cookie_header,
)

app = typer.Typer(
    help="212 Card transactions (private API; requires browser session cookies)"
)
console = Console()


@app.callback()
def cards_callback() -> None:
    """212 Card commands backed by the private cards web API."""


def _utc_boundary(
    date: datetime, tz: ZoneInfo, *, end_of_day: bool = False
) -> datetime:
    """Convert a naive date into a UTC datetime boundary in ``tz``.

    ``--from``/``--to`` are inclusive calendar days in the display timezone:
    midnight of ``date`` for the start, midnight of the following day
    (exclusive boundary) for ``--to``.
    """
    if end_of_day:
        date = date + timedelta(days=1)
    return date.replace(tzinfo=tz).astimezone(timezone.utc)


@app.command("transactions")
def cards_transactions(
    start: datetime = typer.Option(
        ..., "--from", formats=["%Y-%m-%d"], help="Start date (inclusive; in --tz)"
    ),
    end: Optional[datetime] = typer.Option(
        None,
        "--to",
        formats=["%Y-%m-%d"],
        help="End date (inclusive day; in --tz; default today)",
    ),
    output_format: str = typer.Option(
        "json", "--format", help="Output format: json | md | csv"
    ),
    tz_name: str = typer.Option(
        "Europe/Berlin", "--tz", help="IANA timezone for period boundaries and display"
    ),
    cookie_file: Optional[str] = typer.Option(
        None,
        "--cookie-file",
        help="Playwright storage state JSON (playwright-cli state-save <file>); "
        "also via T212_CARDS_COOKIE_FILE",
    ),
    cookie: Optional[str] = typer.Option(
        None, "--cookie", help="Raw Cookie header value; also via T212_CARDS_COOKIES"
    ),
) -> None:
    """Fetch 212 Card transactions for a period from the private cards API."""
    if output_format not in ("json", "md", "csv"):
        console.print("[red]Error: --format must be one of: json, md, csv[/red]")
        raise typer.Exit(code=1)

    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        console.print(f"[red]Error: unknown timezone {tz_name!r}[/red]")
        raise typer.Exit(code=1)

    end_date = end or datetime.combine(datetime.now(tz).date(), time.min)
    start_utc = _utc_boundary(start, tz)
    end_utc = _utc_boundary(end_date, tz, end_of_day=True)
    if start_utc >= end_utc:
        console.print("[red]Error: --from must be before --to[/red]")
        raise typer.Exit(code=1)

    try:
        cookie_header = resolve_cookie_header(cookie_file=cookie_file, cookie=cookie)
    except (ValueError, OSError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)

    client = CardsClient(cookie_header=cookie_header)
    try:
        transactions = list(client.iter_transactions(start_utc, end_utc))
    except CardSessionExpiredError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error fetching card transactions: {e}[/red]")
        raise typer.Exit(code=1)

    if output_format == "json":
        console.print_json(
            json.dumps(
                [tx.model_dump(exclude_none=True) for tx in transactions], default=str
            )
        )
    elif output_format == "md":
        print(
            render_markdown(
                transactions,
                tz,
                from_date=f"{start:%Y-%m-%d}",
                to_date=f"{end_date:%Y-%m-%d}",
            )
        )
    else:
        print(render_csv(transactions, tz), end="")
