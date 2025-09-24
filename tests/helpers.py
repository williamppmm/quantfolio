"""Shared helpers for backend tests."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Sequence

import pandas as pd


def make_market_dataframe(
    closes: Sequence[float | int | None],
    *,
    start: date | str = date(2024, 1, 1),
    tz: str | None = "UTC",
    opens: Sequence[float | int | None] | None = None,
    highs: Sequence[float | int | None] | None = None,
    lows: Sequence[float | int | None] | None = None,
    volumes: Sequence[int | float | None] | None = None,
) -> pd.DataFrame:
    """Create a pandas DataFrame similar to what yfinance.download returns."""

    if isinstance(start, str):
        start_date = pd.Timestamp(start).date()
    else:
        start_date = start

    periods = len(closes)
    index = pd.date_range(start=start_date, periods=periods, freq="D", tz=tz)

    def _ensure(values: Sequence[float | int | None] | None, fallback: Iterable[float | int | None]):
        if values is None:
            return list(fallback)
        if len(values) != periods:
            raise ValueError("Custom OHLC data must match closes length")
        return list(values)

    opens_values = _ensure(opens, closes)
    highs_values = _ensure(highs, closes)
    lows_values = _ensure(lows, closes)
    volume_values = list(volumes) if volumes is not None else [1_000 for _ in range(periods)]

    frame = pd.DataFrame(
        {
            "Open": opens_values,
            "High": highs_values,
            "Low": lows_values,
            "Close": closes,
            "Volume": volume_values,
        },
        index=index,
    )
    return frame


def make_history_payload(
    closes: Sequence[float | int | None],
    *,
    ticker: str = "TEST",
    start: date | str = date(2024, 1, 1),
) -> dict:
    """Build the payload shape returned by get_history used in calculation services."""

    if isinstance(start, str):
        start_date = pd.Timestamp(start).date()
    else:
        start_date = start

    records = []
    current = start_date
    for close in closes:
        records.append({"date": current.isoformat(), "close": None if close is None else float(close)})
        current += timedelta(days=1)

    return {
        "ticker": ticker,
        "start": records[0]["date"] if records else start_date.isoformat(),
        "end": records[-1]["date"] if records else None,
        "count": len(records),
        "data": records,
    }
