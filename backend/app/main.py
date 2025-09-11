from datetime import date
from fastapi import FastAPI, Query
from .services.market_data import get_last_close, get_history
from .services.calculations.metrics import basic_metrics  # ⬅️ nuevo

app = FastAPI(title="Portfolio Manager API")

@app.get("/")
def root():
    return {"message": "Portfolio Manager API running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/prices/{ticker}/last")
def last_price(ticker: str):
    return get_last_close(ticker)

@app.get("/prices/{ticker}/range")
def price_range(
    ticker: str,
    start: date,
    end: date | None = None,
    interval: str = Query("1d", pattern="^(1d|1wk|1mo)$"),
):
    return get_history(ticker, start, end, interval)

@app.get("/metrics/{ticker}/basic")  # ⬅️ nuevo
def metrics_basic(
    ticker: str,
    start: date,
    end: date | None = None,
    rf: float = 0.0,  # tasa libre de riesgo anual (0.0 = 0%)
):
    return basic_metrics(ticker, start, end, rf)