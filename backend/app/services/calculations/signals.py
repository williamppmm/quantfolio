from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import HTTPException

from ..market_data import get_history
from .metrics import _round


def _rsi(series: pd.Series, period: int = 14) -> Optional[float]:
    if len(series) < period + 1:
        return None
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    value = float(rsi.iloc[-1])
    if np.isnan(value):
        return None
    return value


def tech_signals(
    ticker: str,
    start: date,
    end: Optional[date] = None,
    window: int = 60,
    fast: int = 20,
    slow: int = 50,
    rsi_period: int = 14,
) -> dict:
    payload = get_history(ticker, start, end, interval="1d")
    minimum_required = max(window, slow) + 1
    if payload["count"] < minimum_required:
        raise HTTPException(
            status_code=404,
            detail=f"Not enough data for {ticker}; need at least {minimum_required} points",
        )

    df = pd.DataFrame(payload["data"])
    if "close" not in df.columns:
        raise HTTPException(status_code=500, detail="close column missing from data")

    closes = df["close"].astype(float)

    momentum = float(closes.pct_change(window).iloc[-1])

    sma_fast_series = closes.rolling(fast).mean()
    sma_slow_series = closes.rolling(slow).mean()
    sma_fast = float(sma_fast_series.iloc[-1])
    sma_slow = float(sma_slow_series.iloc[-1])

    cross_now = bool(sma_fast > sma_slow)

    cross_flag = (sma_fast_series > sma_slow_series).astype(int)
    cross_change = cross_flag.diff()
    last_change = cross_change.dropna()
    if last_change.empty or (last_change != 0).sum() == 0:
        last_cross_date = None
        last_cross_type = None
    else:
        idx_last = last_change[last_change != 0].index[-1]
        last_cross_date = str(df.loc[idx_last, "date"]) if "date" in df.columns else str(idx_last.date())
        last_cross_type = "golden" if last_change.loc[idx_last] > 0 else "death"

    rsi_value = _rsi(closes, rsi_period)

    return {
        "ticker": payload["ticker"],
        "start": payload["start"],
        "end": payload["end"],
        "count": int(payload["count"]),
        "price": _round(closes.iloc[-1]),
        "momentum_window": int(window),
        "momentum": _round(momentum),
        "sma_fast_window": int(fast),
        "sma_fast": _round(sma_fast),
        "sma_slow_window": int(slow),
        "sma_slow": _round(sma_slow),
        "cross_now": cross_now,
        "last_cross_date": last_cross_date,
        "last_cross_type": last_cross_type,
        "rsi_period": int(rsi_period),
        "rsi": _round(rsi_value),
    }
