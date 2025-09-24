from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import HTTPException

from ..market_data import get_history

TRADING_DAYS = 252


def _round(value: Optional[float], ndigits: int = 6) -> Optional[float]:
    if value is None:
        return None
    return float(round(float(value), ndigits))


def _require_close_column(df: pd.DataFrame) -> None:
    if "close" not in df.columns:
        raise HTTPException(status_code=500, detail="close column missing from data")


def _ensure_enough_points(ticker: str, count: int) -> None:
    if count < 2:
        raise HTTPException(status_code=404, detail=f"Not enough data for {ticker}")


def basic_metrics(ticker: str, start: date, end: Optional[date] = None, rf: float = 0.0) -> dict:
    """Return annualised return, volatility, Sharpe and max drawdown for a ticker."""
    payload = get_history(ticker, start, end, interval="1d")
    _ensure_enough_points(ticker, payload["count"])

    df = pd.DataFrame(payload["data"])
    _require_close_column(df)

    df["close"] = df["close"].astype(float)
    df["ret"] = df["close"].pct_change()
    rets = df["ret"].dropna()
    if rets.empty:
        raise HTTPException(status_code=404, detail=f"Not enough data for {ticker}")

    mean_daily = float(rets.mean())
    std_daily = float(rets.std(ddof=1))
    ann_return = float((1 + mean_daily) ** TRADING_DAYS - 1)
    ann_vol = float(std_daily * np.sqrt(TRADING_DAYS))

    if rf != 0.0:
        rf_daily = (1 + rf) ** (1 / TRADING_DAYS) - 1
    else:
        rf_daily = 0.0
    excess_daily = rets - rf_daily
    ann_excess = float(excess_daily.mean() * TRADING_DAYS)
    sharpe = ann_excess / ann_vol if ann_vol > 0 else None

    equity = (1 + rets).cumprod()
    peak = equity.cummax()
    drawdown = (equity / peak) - 1.0
    max_dd = float(drawdown.min()) if not drawdown.empty else 0.0

    return {
        "ticker": payload["ticker"],
        "start": payload["start"],
        "end": payload["end"],
        "n": int(payload["count"]),
        "ann_return": _round(ann_return),
        "ann_volatility": _round(ann_vol),
        "sharpe": _round(sharpe),
        "max_drawdown": _round(max_dd),
        "rf": float(rf),
    }


def advanced_metrics(
    ticker: str,
    start: date,
    end: Optional[date] = None,
    rf: float = 0.0,
    mar: float = 0.0,
) -> dict:
    """Return advanced metrics extending the basic set with downside metrics and YTD."""
    payload = get_history(ticker, start, end, interval="1d")
    _ensure_enough_points(ticker, payload["count"])

    df = pd.DataFrame(payload["data"])
    _require_close_column(df)
    df["close"] = df["close"].astype(float)
    df["ret"] = df["close"].pct_change()
    rets = df["ret"].dropna()
    if rets.empty:
        raise HTTPException(status_code=404, detail=f"Not enough data for {ticker}")

    mean_daily = float(rets.mean())
    std_daily = float(rets.std(ddof=1))
    ann_return = float((1 + mean_daily) ** TRADING_DAYS - 1)
    ann_vol = float(std_daily * np.sqrt(TRADING_DAYS))

    if rf != 0.0:
        rf_daily = (1 + rf) ** (1 / TRADING_DAYS) - 1
    else:
        rf_daily = 0.0
    excess_daily = rets - rf_daily
    ann_excess = float(excess_daily.mean() * TRADING_DAYS)
    sharpe = ann_excess / ann_vol if ann_vol > 0 else None

    equity = (1 + rets).cumprod()
    peak = equity.cummax()
    drawdown = (equity / peak) - 1.0
    max_dd = float(drawdown.min()) if not drawdown.empty else 0.0

    if mar != 0.0:
        mar_daily = (1 + mar) ** (1 / TRADING_DAYS) - 1
    else:
        mar_daily = 0.0
    downside = rets[rets < mar_daily]
    if downside.empty:
        downside_vol_daily = 0.0
    else:
        downside_vol_daily = float(downside.std(ddof=1))
    downside_vol_ann = downside_vol_daily * np.sqrt(TRADING_DAYS) if downside_vol_daily > 0 else None

    sortino = None
    if downside_vol_ann and downside_vol_ann > 0:
        sortino = (ann_return - mar) / downside_vol_ann

    calmar = None
    if max_dd < 0:
        calmar = ann_return / abs(max_dd)

    if payload["end"] is None:
        end_date = pd.to_datetime(df["date"].iloc[-1]).date()
    else:
        end_date = pd.to_datetime(payload["end"]).date()
    ytd_start = date(end_date.year, 1, 1)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df_ytd = df[df["date"] >= ytd_start]
    if len(df_ytd) >= 2:
        ytd_return = float(df_ytd["close"].iloc[-1] / df_ytd["close"].iloc[0] - 1.0)
    else:
        ytd_return = None

    return {
        "ticker": payload["ticker"],
        "start": payload["start"],
        "end": payload["end"],
        "n": int(payload["count"]),
        "ann_return": _round(ann_return),
        "ann_volatility": _round(ann_vol),
        "sharpe": _round(sharpe),
        "max_drawdown": _round(max_dd),
        "rf": float(rf),
        "mar": float(mar),
        "downside_volatility": _round(downside_vol_ann),
        "sortino": _round(sortino),
        "calmar": _round(calmar),
        "ytd_return": _round(ytd_return),
    }
