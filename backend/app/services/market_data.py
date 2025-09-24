import math
from datetime import date
from typing import Optional

from fastapi import HTTPException
import yfinance as yf


def _safe_float(value: object) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result):
        return None
    return round(result, 6)


def _safe_int(value: object) -> Optional[int]:
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(as_float):
        return None
    return int(as_float)


def _normalize_index(df) -> None:
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)


def get_last_close(ticker: str) -> dict:
    """Return the latest adjusted close for the given ticker."""
    try:
        df = yf.download(
            tickers=ticker,
            period="7d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as exc:  # pragma: no cover - upstream failure
        raise HTTPException(status_code=502, detail=f"Error downloading data: {exc}") from exc

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data available for ticker {ticker}")

    df = df.dropna(how="all")
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No valid prices for ticker {ticker}")

    _normalize_index(df)

    last_ts = df.index[-1]
    last_row = df.iloc[-1]
    close_value = _safe_float(last_row.get("Close"))
    if close_value is None:
        raise HTTPException(status_code=404, detail=f"No close price for ticker {ticker}")

    return {
        "ticker": ticker.upper(),
        "date": last_ts.date().isoformat(),
        "close": close_value,
    }


def get_history(ticker: str, start: date, end: Optional[date] = None, interval: str = "1d") -> dict:
    if end is not None and start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end")

    try:
        df = yf.download(
            tickers=ticker,
            start=start.isoformat(),
            end=None if end is None else end.isoformat(),
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=True,
        )
    except Exception as exc:  # pragma: no cover - upstream failure
        raise HTTPException(status_code=502, detail=f"Error downloading data: {exc}") from exc

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker} in the requested range")

    df = df.dropna(how="all")
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker} in the requested range")

    _normalize_index(df)

    columns = {col.lower(): col for col in df.columns}
    open_key = columns.get("open")
    high_key = columns.get("high")
    low_key = columns.get("low")
    close_key = columns.get("close") or columns.get("adj close")
    volume_key = columns.get("volume")

    if close_key is None:
        raise HTTPException(status_code=500, detail="close column missing from provider response")

    records = []
    for idx, row in df.iterrows():
        item = {"date": idx.date().isoformat()}

        close_value = _safe_float(row.get(close_key))
        if close_value is None:
            continue

        item["close"] = close_value

        if open_key and high_key and low_key:
            item["open"] = _safe_float(row.get(open_key))
            item["high"] = _safe_float(row.get(high_key))
            item["low"] = _safe_float(row.get(low_key))

        if volume_key:
            item["volume"] = _safe_int(row.get(volume_key))
        else:
            item["volume"] = None

        records.append(item)

    if not records:
        raise HTTPException(status_code=404, detail=f"No data for {ticker} in the requested range")

    return {
        "ticker": ticker.upper(),
        "interval": interval,
        "start": start.isoformat(),
        "end": None if end is None else end.isoformat(),
        "count": len(records),
        "data": records,
    }
