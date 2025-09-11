# backend/app/services/market_data.py

from datetime import date
from typing import Optional
from fastapi import HTTPException
import yfinance as yf

def get_last_close(ticker: str) -> dict:
    """Devuelve el cierre más reciente (ajustado) del ticker."""
    try:
        df = yf.download(
            tickers=ticker,
            period="7d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al descargar datos: {e}")

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No hay datos para el ticker: {ticker}")

    df = df.dropna()
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Sin precios válidos para: {ticker}")

    # Normaliza índice con zona horaria (si aplica)
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)

    last_ts = df.index[-1]
    last_row = df.iloc[-1]
    return {
        "ticker": ticker.upper(),
        "date": last_ts.date().isoformat(),
        "close": float(round(last_row["Close"], 6)),
    }

def get_history(ticker: str, start: date, end: Optional[date] = None, interval: str = "1d") -> dict:
    if end is not None and start > end:
        raise HTTPException(status_code=400, detail="start debe ser <= end")
    try:
        df = yf.download(
            tickers=ticker,
            start=start.isoformat(),
            end=None if end is None else end.isoformat(),
            interval=interval,         # admite: "1d", "1wk", "1mo"
            auto_adjust=False,          # devueve OHLC sin ajustar
            progress=False,
            threads=True,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al descargar datos: {e}")

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"Sin datos para {ticker} en el rango solicitado")

    df = df.dropna()
    # Normaliza índice con zona horaria (si aplica)
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)

    records = []
    cols = df.columns
    for idx, row in df.iterrows():
        item = {"date": idx.date().isoformat()}
        # Si tenemos OHLC, los enviamos; si no, al menos Close
        if {"Open", "High", "Low", "Close"}.issubset(cols):
            item.update({
                "open": float(round(row["Open"], 6)),
                "high": float(round(row["High"], 6)),
                "low":  float(round(row["Low"], 6)),
                "close": float(round(row["Close"], 6)),
                "volume": int(row.get("Volume", 0)) if "Volume" in cols and row.get("Volume") == row.get("Volume") else 0,
            })
        else:
            item["close"] = float(row["Close"])
        records.append(item)

    return {
        "ticker": ticker.upper(),
        "interval": interval,
        "start": start.isoformat(),
        "end": None if end is None else end.isoformat(),
        "count": len(records),
        "data": records,
    }