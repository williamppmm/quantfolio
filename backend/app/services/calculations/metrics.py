# backend/app/services/calculations/metrics.py

from datetime import date
from typing import Optional
from fastapi import HTTPException
import numpy as np
import pandas as pd
from ..market_data import get_history

TRADING_DAYS = 252

def _r(x, nd: int = 6):
    return None if x is None else float(round(x, nd))

def basic_metrics(ticker: str, start: date, end: Optional[date] = None, rf: float = 0.0) -> dict:
    """
    Métricas básicas a partir de cierres diarios:
    - Retorno anualizado
    - Volatilidad anualizada
    - Sharpe (sobre rf)
    - Máximo drawdown
    """
    payload = get_history(ticker, start, end, interval="1d")
    if payload["count"] < 2:
        raise HTTPException(status_code=400, detail="Se requieren al menos 2 datos de cierre.")

    df = pd.DataFrame(payload["data"])
    if "close" not in df.columns:
        raise HTTPException(status_code=500, detail="No se encontró la columna 'close' en los datos.")

    df["ret"] = df["close"].pct_change()
    rets = df["ret"].dropna()
    if rets.empty:
        raise HTTPException(status_code=400, detail="No hay retornos válidos para el rango indicado.")

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
    sharpe = float(ann_excess / ann_vol) if ann_vol > 0 else None

    equity = (1 + rets).cumprod()
    peak = equity.cummax()
    drawdown = (equity / peak) - 1.0
    max_dd = float(drawdown.min())

    return {
        "ticker": payload["ticker"],
        "start": payload["start"],
        "end": payload["end"],
        "n": int(payload["count"]),
        "ann_return": _r(ann_return),
        "ann_volatility": _r(ann_vol),
        "sharpe": _r(sharpe),
        "max_drawdown": _r(max_dd),
        "rf": float(rf),
    }

def advanced_metrics(ticker: str, start: date, end: Optional[date] = None, rf: float = 0.0, mar: float = 0.0) -> dict:
    """
    Métricas avanzadas:
    - Básicas (ann_return, ann_volatility, sharpe, max_drawdown)
    - Downside volatility (anual) y Sortino (sobre MAR anual)
    - Calmar ratio
    - YTD return
    """
    payload = get_history(ticker, start, end, interval="1d")
    if payload["count"] < 2:
        raise HTTPException(status_code=400, detail="Se requieren al menos 2 datos de cierre.")

    df = pd.DataFrame(payload["data"])
    if "close" not in df.columns:
        raise HTTPException(status_code=500, detail="No se encontró la columna 'close' en los datos.")

    df["ret"] = df["close"].pct_change()
    rets = df["ret"].dropna()
    if rets.empty:
        raise HTTPException(status_code=400, detail="No hay retornos válidos para el rango indicado.")

    # Básicos
    mean_daily = float(rets.mean())
    std_daily = float(rets.std(ddof=1))
    ann_return = float((1 + mean_daily) ** TRADING_DAYS - 1)
    ann_vol = float(std_daily * np.sqrt(TRADING_DAYS))

    # Sharpe sobre rf anual
    if rf != 0.0:
        rf_daily = (1 + rf) ** (1 / TRADING_DAYS) - 1
    else:
        rf_daily = 0.0
    excess_daily = rets - rf_daily
    ann_excess = float(excess_daily.mean() * TRADING_DAYS)
    sharpe = float(ann_excess / ann_vol) if ann_vol > 0 else None

    # Drawdown
    equity = (1 + rets).cumprod()
    peak = equity.cummax()
    drawdown = (equity / peak) - 1.0
    max_dd = float(drawdown.min())

    # Downside vol y Sortino con MAR anual
    if mar != 0.0:
        mar_daily = (1 + mar) ** (1 / TRADING_DAYS) - 1
    else:
        mar_daily = 0.0
    downside = rets[rets < mar_daily]
    if downside.empty:
        downside_vol_ann = 0.0
        sortino = None if ann_return is None else float((ann_return - mar) / 1e-12)
    else:
        downside_vol_daily = float(downside.std(ddof=1))
        downside_vol_ann = float(downside_vol_daily * np.sqrt(TRADING_DAYS))
        sortino = float((ann_return - mar) / downside_vol_ann) if downside_vol_ann > 0 else None

    # Calmar
    calmar = float(ann_return / abs(max_dd)) if max_dd < 0 else None

    # YTD
    end_str = payload["end"]
    if end_str is None and len(df) > 0:
        end_year = pd.to_datetime(df["date"].iloc[-1]).year
    else:
        end_year = pd.to_datetime(end_str if end_str else pd.Timestamp.today().date()).year
    ytd_start = pd.Timestamp(f"{end_year}-01-01").date()

    df_ytd = df[pd.to_datetime(df["date"]).dt.date >= ytd_start]
    if len(df_ytd) >= 2:
        ytd_return = float(df_ytd["close"].iloc[-1] / df_ytd["close"].iloc[0] - 1.0)
    else:
        ytd_return = None

    return {
        "ticker": payload["ticker"],
        "start": payload["start"],
        "end": payload["end"],
        "n": int(payload["count"]),
        "ann_return": _r(ann_return),
        "ann_volatility": _r(ann_vol),
        "sharpe": _r(sharpe),
        "max_drawdown": _r(max_dd),
        "rf": float(rf),
        "mar": float(mar),
        "downside_volatility": _r(downside_vol_ann),
        "sortino": _r(sortino),
        "calmar": _r(calmar),
        "ytd_return": _r(ytd_return),
    }