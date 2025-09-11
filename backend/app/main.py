# backend/app/main.py

from datetime import date
from fastapi import FastAPI, Query

from .services.market_data import get_last_close, get_history
from .services.calculations.metrics import basic_metrics, advanced_metrics
from .services.calculations.signals import tech_signals
from .schemas import (
    MessageResponse, HealthResponse, LastPriceResponse,
    HistoryResponse, BasicMetricsResponse, AdvancedMetricsResponse,
    TechSignalsResponse
)

app = FastAPI(title="Portfolio Manager API", version="0.1.0")

@app.get("/", response_model=MessageResponse, summary="Root")
def root():
    return {"message": "Portfolio Manager API running"}

@app.get("/health", response_model=HealthResponse, summary="Health")
def health():
    return {"status": "ok"}

@app.get("/prices/{ticker}/last", response_model=LastPriceResponse, summary="Last Price")
def last_price(ticker: str):
    return get_last_close(ticker)

@app.get("/prices/{ticker}/range", response_model=HistoryResponse, summary="Price Range")
def price_range(
    ticker: str,
    start: date,
    end: date | None = None,
    interval: str = Query("1d", pattern="^(1d|1wk|1mo)$"),
):
    return get_history(ticker, start, end, interval)

@app.get("/metrics/{ticker}/basic", response_model=BasicMetricsResponse, summary="Basic Metrics")
def metrics_basic(
    ticker: str,
    start: date,
    end: date | None = None,
    rf: float = 0.0,
):
    return basic_metrics(ticker, start, end, rf)

@app.get("/metrics/{ticker}/advanced", response_model=AdvancedMetricsResponse, summary="Advanced Metrics")
def metrics_advanced(
    ticker: str,
    start: date,
    end: date | None = None,
    rf: float = 0.0,
    mar: float = 0.0,
):
    return advanced_metrics(ticker, start, end, rf, mar)

@app.get("/signals/{ticker}/tech", response_model=TechSignalsResponse, summary="Technical Signals (Momentum & SMA Cross)")
def signals_tech(
    ticker: str,
    start: date,
    end: date | None = None,
    window: int = 60,
    fast: int = 20,
    slow: int = 50,
    rsi_period: int = 14,
):
    return tech_signals(ticker, start, end, window, fast, slow, rsi_period)