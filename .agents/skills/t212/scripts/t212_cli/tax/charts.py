"""ASCII chart rendering for historical value series.

No external plotting deps — uses Unicode block characters and the existing
rich console. Designed for terminal output, two modes:

1. `render_sparkline` — tiny inline strip (one row of blocks)
2. `render_line_chart` — full multi-row chart with Y-axis labels and grid

Both work on any pandas Series indexed by date.
"""

from __future__ import annotations

import datetime
from typing import Sequence, TypedDict

import numpy as np
import pandas as pd
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

_BLOCKS = "▁▂▃▄▅▆▇█"
_GRID_CHARS = {"h": "─", "v": "│", "tl": "┌", "tr": "┐", "bl": "└", "br": "┘"}


class SummaryRow(TypedDict):
    """Row payload for `render_summary_table`."""

    ticker: str
    symbol: str
    name: str
    start_value: float
    end_value: float
    pct_change: float
    values: Sequence[float]


def render_sparkline(values: Sequence[float]) -> str:
    """Render a one-line sparkline from a sequence of values.

    NaN values are rendered as gaps (no block). If all values are NaN or
    the sequence is empty, returns an empty string.
    """
    clean = [v for v in values if not (isinstance(v, float) and v != v)]
    if not clean:
        return ""
    lo = min(clean)
    hi = max(clean)
    if hi == lo:
        return _BLOCKS[-1] * len(clean)
    scale = (len(_BLOCKS) - 1) / (hi - lo)
    chars: list[str] = []
    for v in values:
        if isinstance(v, float) and v != v:
            chars.append(" ")
            continue
        idx = max(0, min(len(_BLOCKS) - 1, int((v - lo) * scale)))
        chars.append(_BLOCKS[idx])
    return "".join(chars)


def _fmt_value(v: float, width: int) -> str:
    """Format a value for axis labels, fitting within width."""
    s = f"{v:,.2f}"
    return s.rjust(width)


def render_line_chart(
    series: pd.Series,
    *,
    title: str | None = None,
    width: int = 72,
    height: int = 16,
    currency: str = "",
    color: str = "cyan",
    console: Console | None = None,
) -> None:
    """Render a full ASCII line chart for a date-indexed value series.

    Args:
        series: pandas Series indexed by date/datetime, float values.
        title: Optional chart title.
        width: Chart width in characters (excluding Y-axis labels).
        height: Chart height in rows.
        currency: Currency code appended to axis labels (e.g. "EUR").
        color: rich color name for the chart body.
        console: Console to print to. If None, a new Console is created.
    """
    cons = console or Console()

    clean = series.dropna()
    if clean.empty:
        cons.print(f"[yellow]No data to chart for '{title or 'series'}'.[/yellow]")
        return

    values = clean.to_numpy()
    if len(values) > width:
        # Resample (nearest sample) to fit width
        idx = np.linspace(0, len(values) - 1, width)
        sampled = [values[int(i)] for i in idx]
    else:
        sampled = list(values)

    n = len(sampled)
    lo = float(min(sampled))
    hi = float(max(sampled))
    if hi == lo:
        hi = lo + 1.0

    label_w = max(len(_fmt_value(hi, 0)), len(_fmt_value(lo, 0))) + len(currency) + 1

    lines: list[Text] = []
    for row in range(height - 1, -1, -1):
        threshold = lo + (hi - lo) * row / (height - 1)
        chars: list[str] = []
        for v in sampled:
            chars.append("█" if v >= threshold else " ")
        body = "".join(chars)

        if row == height - 1:
            label = f"{_fmt_value(hi, label_w)} {currency}"
        elif row == 0:
            label = f"{_fmt_value(lo, label_w)} {currency}"
        elif row == height // 2:
            mid = lo + (hi - lo) / 2
            label = f"{_fmt_value(mid, label_w)} {currency}"
        else:
            label = " " * (label_w + 1)

        axis = "┤" if row in (height - 1, 0, height // 2) else "│"
        line = Text()
        line.append(f"{label} {axis}", style="dim")
        line.append(body, style=color)
        lines.append(line)

    # X-axis baseline
    baseline = Text()
    baseline.append(" " * (label_w + 1) + "└", style="dim")
    baseline.append(_GRID_CHARS["h"] * n, style="dim")
    lines.append(baseline)

    # X-axis date labels (start / mid / end)
    idx = clean.index
    start_d = pd.Timestamp(idx.min()).date()
    end_d = pd.Timestamp(idx.max()).date()
    mid_d = start_d + (end_d - start_d) // 2

    date_line = Text()
    date_line.append(" " * (label_w + 1), style="dim")
    date_line.append(start_d.isoformat(), style="dim")
    gap = max(1, n - 2 * 10 - len(start_d.isoformat()) - len(end_d.isoformat()))
    date_line.append(" " * (gap // 2), style="dim")
    date_line.append(mid_d.isoformat(), style="dim")
    date_line.append(" " * (gap - gap // 2), style="dim")
    date_line.append(end_d.isoformat(), style="dim")
    lines.append(date_line)

    group = Group(*lines)
    if title:
        cons.print(Panel(group, title=f"[bold]{title}[/bold]", border_style="dim"))
    else:
        cons.print(group)


def render_summary_table(
    rows: list[SummaryRow],
    *,
    currency: str = "",
    console: Console | None = None,
) -> None:
    """Render a summary table for multiple series.

    Each row should have: name, symbol, start, last, abs_change, pct_change,
    sparkline.
    """
    cons = console or Console()
    table = Table(show_lines=False, expand=False)
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Yahoo", style="dim")
    table.add_column("Fund", style="white", overflow="fold", max_width=32)
    table.add_column(f"Start ({currency})", justify="right")
    table.add_column(f"Latest ({currency})", justify="right", style="bold")
    table.add_column("Δ", justify="right")
    table.add_column("Sparkline")

    for r in rows:
        pct = r["pct_change"]
        color = "green" if pct >= 0 else "red"
        arrow = "▲" if pct >= 0 else "▼"
        table.add_row(
            r["ticker"],
            r["symbol"],
            r["name"],
            f"{r['start_value']:,.2f}",
            f"{r['end_value']:,.2f}",
            f"[{color}]{arrow} {pct:+5.2f}%[/{color}]",
            f"[{color}]{render_sparkline(list(r['values']))}[/{color}]",
        )
    cons.print(table)


def fmt_date_range(start: datetime.date, end: datetime.date) -> str:
    """Format a human-readable date range."""
    n_days = (end - start).days
    return f"{start.isoformat()} → {end.isoformat()}  ({n_days} days)"
