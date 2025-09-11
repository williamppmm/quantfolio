from datetime import date
from fastapi import HTTPException
import numpy as np
import pandas as pd

# Reutilizamos el histórico del servicio de mercado
from ..market_data import get_history

TRADING_DAYS = 252

def basic_metrics(ticker: str, start: date, end: date | None = None, rf: float = 0.0) -> dict:
    """
    Calcula métricas simples a partir de cierres diarios:
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

    # Retorno y volatilidad anualizados
    mean_daily = float(rets.mean())
    std_daily = float(rets.std(ddof=1))  # ddof=1 para sample std
    ann_ret = float((1 + mean_daily) ** TRADING_DAYS - 1)
    ann_vol = float(std_daily * np.sqrt(TRADING_DAYS))

    # Sharpe sobre rf (rf anual como decimal, p.ej. 0.02 = 2%)
    if rf != 0.0:
        rf_daily = (1 + rf) ** (1 / TRADING_DAYS) - 1
    else:
        rf_daily = 0.0
    excess_daily = rets - rf_daily
    ann_excess = float(excess_daily.mean() * TRADING_DAYS)
    sharpe = float(ann_excess / ann_vol) if ann_vol > 0 else None

    # Máximo drawdown
    equity = (1 + rets).cumprod()
    peak = equity.cummax()
    drawdown = (equity / peak) - 1.0
    max_dd = float(drawdown.min())

    return {
        "ticker": payload["ticker"],
        "start": payload["start"],
        "end": payload["end"],
        "n": int(payload["count"]),
        "ann_return": ann_ret,
        "ann_volatility": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "rf": rf,
    }