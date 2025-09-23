from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, timedelta
import logging
from typing import AsyncIterator, List
from uuid import UUID

from fastapi import FastAPI, HTTPException, Path, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .core.settings import get_settings
from .db import crud_portfolios, crud_prices, crud_transactions
from .db.errors import (
    InvalidTransactionError,
    PortfolioAlreadyExistsError,
    PortfolioNotFoundError,
    TransactionNotFoundError,
)
from .db.session import check_connection, get_sessionmaker
from .schemas import (
    AdvancedMetricsResponse,
    BasicMetricsResponse,
    HealthResponse,
    HistoryResponse,
    LastDbPriceResponse,
    LastPriceResponse,
    MessageResponse,
    PortfolioCreate,
    PortfolioListResponse,
    PortfolioMetricsResponse,
    PortfolioOut,
    PositionOut,
    TechSignalsResponse,
    TransactionCreate,
    TransactionListResponse,
    TransactionOut,
)
from .services.calculations.metrics import advanced_metrics, basic_metrics
from .services.calculations.signals import tech_signals
from .services.market_data import get_history, get_last_close
from .services.portfolios import compute_portfolio_metrics, compute_positions


settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


app = FastAPI(title="Portfolio Manager API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=MessageResponse, summary="Root")
def root() -> MessageResponse:
    return MessageResponse(message="Portfolio Manager API running")


@app.get("/health", response_model=HealthResponse, summary="Health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/ready", response_model=HealthResponse, summary="Readiness check")
async def ready() -> HealthResponse:
    try:
        await check_connection()
    except SQLAlchemyError as exc:  # pragma: no cover - infrastructure failure
        logger.exception("Database readiness check failed")
        raise HTTPException(status_code=503, detail="Database not ready") from exc
    return HealthResponse(status="ok")


@app.get("/prices/{ticker}/last", response_model=LastPriceResponse, summary="Last Price")
def last_price(ticker: str) -> LastPriceResponse:
    return LastPriceResponse(**get_last_close(ticker))


@app.get("/prices/{ticker}/range", response_model=HistoryResponse, summary="Price Range")
def price_range(
    ticker: str,
    start: date,
    end: date | None = None,
    interval: str = Query("1d", pattern="^(1d|1wk|1mo)$"),
) -> HistoryResponse:
    return HistoryResponse(**get_history(ticker, start, end, interval))


@app.get("/metrics/{ticker}/basic", response_model=BasicMetricsResponse, summary="Basic Metrics")
def metrics_basic(
    ticker: str,
    start: date,
    end: date | None = None,
    rf: float = 0.0,
) -> BasicMetricsResponse:
    return BasicMetricsResponse(**basic_metrics(ticker, start, end, rf))


@app.get("/metrics/{ticker}/advanced", response_model=AdvancedMetricsResponse, summary="Advanced Metrics")
def metrics_advanced(
    ticker: str,
    start: date,
    end: date | None = None,
    rf: float = 0.0,
    mar: float = 0.0,
) -> AdvancedMetricsResponse:
    return AdvancedMetricsResponse(**advanced_metrics(ticker, start, end, rf, mar))


@app.get(
    "/signals/{ticker}/tech",
    response_model=TechSignalsResponse,
    summary="Technical Signals (Momentum & SMA Cross)",
)
def signals_tech(
    ticker: str,
    start: date,
    end: date | None = None,
    window: int = 60,
    fast: int = 20,
    slow: int = 50,
    rsi_period: int = 14,
) -> TechSignalsResponse:
    return TechSignalsResponse(
        **tech_signals(ticker, start, end, window, fast, slow, rsi_period)
    )


@app.post("/ingest/{ticker}", summary="Ingest historical prices into DB (UPSERT)")
async def ingest_prices(
    ticker: str,
    start: date,
    end: date | None = None,
    interval: str = Query("1d", pattern="^(1d|1wk|1mo)$"),
) -> dict:
    payload = get_history(ticker, start, end, interval)
    rows = payload.get("data", [])
    if not rows:
        raise HTTPException(status_code=404, detail="No data to ingest")

    async with session_scope() as session:
        async with session.begin():
            affected = await crud_prices.upsert_prices(session, ticker, rows)

    return {
        "ticker": payload["ticker"],
        "interval": payload["interval"],
        "start": payload["start"],
        "end": payload["end"],
        "ingested": len(rows),
        "upsert_effect": affected,
    }


@app.get(
    "/prices/{ticker}/db/range",
    response_model=HistoryResponse,
    summary="Read prices from DB (range)",
)
async def db_price_range(
    ticker: str,
    start: date,
    end: date | None = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> HistoryResponse:
    async with session_scope() as session:
        total = await crud_prices.count_prices_range(session, ticker, start, end)
        rows = await crud_prices.read_prices_range_paged(session, ticker, start, end, limit=limit, offset=offset)

    records = []
    for record in rows:
        records.append(
            {
                "date": record.date.isoformat(),
                "open": float(record.open) if record.open is not None else None,
                "high": float(record.high) if record.high is not None else None,
                "low": float(record.low) if record.low is not None else None,
                "close": float(record.close) if record.close is not None else None,
                "volume": int(record.volume) if record.volume is not None else None,
            }
        )

    return HistoryResponse(
        ticker=ticker.upper(),
        interval="1d",
        start=start.isoformat(),
        end=None if end is None else end.isoformat(),
        count=len(records),
        data=records,
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/prices/{ticker}/db/last",
    response_model=LastDbPriceResponse,
    summary="Last stored price in DB",
)
async def db_last_price(ticker: str) -> LastDbPriceResponse:
    async with session_scope() as session:
        record = await crud_prices.get_last_price(session, ticker)
    if record is None:
        raise HTTPException(status_code=404, detail="Ticker has no stored prices")
    return LastDbPriceResponse(
        ticker=record.ticker,
        date=record.date,
        close=record.close,
        open=record.open,
        high=record.high,
        low=record.low,
        volume=record.volume,
    )

# 1) Leer la última fecha guardada en DB
@app.post("/ingest/{ticker}/latest", summary="Ingest missing days from last stored date to today")
def ingest_latest(
    ticker: str,
    interval: str = Query("1d", pattern="^(1d|1wk|1mo)$"),
):
    # 1) Leer la última fecha guardada en DB
    last = read_prices_last(ticker.upper())
    if last is None:
        # No hay datos en DB: pedirle al usuario que haga una ingesta inicial por rango
        return {
            "ticker": ticker.upper(),
            "interval": interval,
            "start": None,
            "end": None,
            "ingested": 0,
            "upsert_effect": 0,
            "status": "empty_db_use_range_ingest"
        }

    start = last["date"] + timedelta(days=1)
    end = date.today()

    # Si start > end, ya está al día
    if start > end:
        return {
            "ticker": ticker.upper(),
            "interval": interval,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "ingested": 0,
            "upsert_effect": 0,
            "status": "up_to_date"
        }

    # 2) Descargar desde el proveedor
    payload = get_history(ticker, start, end, interval)

    # 3) Si no hay filas nuevas, responder 200 con ingested=0
    if payload["count"] == 0 or not payload["data"]:
        return {
            "ticker": ticker.upper(),
            "interval": interval,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "ingested": 0,
            "upsert_effect": 0,
            "status": "no_new_rows"
        }

    # 4) UPSERT a DB
    effect = upsert_prices(ticker.upper(), payload["data"])

    return {
        "ticker": ticker.upper(),
        "interval": interval,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "ingested": payload["count"],
        "upsert_effect": effect,
        "status": "ok"
    }

@app.post(
    "/portfolios",
    response_model=PortfolioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create portfolio",
)
async def create_portfolio(payload: PortfolioCreate) -> PortfolioOut:
    async with session_scope() as session:
        async with session.begin():
            try:
                portfolio = await crud_portfolios.create_portfolio(session, name=payload.name)
            except PortfolioAlreadyExistsError:
                raise HTTPException(status_code=409, detail="Portfolio name already exists")
    return PortfolioOut.model_validate(portfolio)


@app.get("/portfolios", response_model=PortfolioListResponse, summary="List portfolios")
async def list_portfolios(
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PortfolioListResponse:
    async with session_scope() as session:
        total = await crud_portfolios.count_portfolios(session)
        portfolios = await crud_portfolios.list_portfolios(session, limit=limit, offset=offset)
    items = [PortfolioOut.model_validate(p) for p in portfolios]
    return PortfolioListResponse(total=total, limit=limit, offset=offset, items=items)


@app.get(
    "/portfolios/{portfolio_id}",
    response_model=PortfolioOut,
    summary="Portfolio detail",
)
async def get_portfolio(portfolio_id: UUID = Path(...)) -> PortfolioOut:
    async with session_scope() as session:
        try:
            portfolio = await crud_portfolios.get_portfolio(session, portfolio_id)
        except PortfolioNotFoundError:
            raise HTTPException(status_code=404, detail="Portfolio not found")
    return PortfolioOut.model_validate(portfolio)


@app.delete(
    "/portfolios/{portfolio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete portfolio",
)
async def delete_portfolio(portfolio_id: UUID = Path(...)) -> Response:
    async with session_scope() as session:
        async with session.begin():
            try:
                await crud_portfolios.delete_portfolio(session, portfolio_id)
            except PortfolioNotFoundError:
                raise HTTPException(status_code=404, detail="Portfolio not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/portfolios/{portfolio_id}/transactions",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create transaction",
)
async def create_transaction(
    portfolio_id: UUID,
    payload: TransactionCreate,
) -> TransactionOut:
    async with session_scope() as session:
        async with session.begin():
            try:
                portfolio = await crud_portfolios.get_portfolio(session, portfolio_id)
            except PortfolioNotFoundError:
                raise HTTPException(status_code=404, detail="Portfolio not found")
            try:
                transaction = await crud_transactions.create_transaction(
                    session,
                    portfolio=portfolio,
                    ticker=payload.ticker,
                    tx_type=payload.type,
                    tx_date=payload.date,
                    quantity=payload.quantity,
                    price=payload.price,
                    amount=payload.amount,
                )
            except InvalidTransactionError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
    return TransactionOut.model_validate(transaction)


@app.get(
    "/portfolios/{portfolio_id}/transactions",
    response_model=TransactionListResponse,
    summary="List transactions",
)
async def list_transactions(
    portfolio_id: UUID,
    start: date | None = Query(None, alias="from"),
    end: date | None = Query(None, alias="to"),
    ticker: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> TransactionListResponse:
    async with session_scope() as session:
        try:
            await crud_portfolios.get_portfolio(session, portfolio_id)
        except PortfolioNotFoundError:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        total = await crud_transactions.count_transactions(
            session,
            portfolio_id=portfolio_id,
            start=start,
            end=end,
            ticker=ticker,
        )
        transactions = await crud_transactions.list_transactions(
            session,
            portfolio_id=portfolio_id,
            start=start,
            end=end,
            ticker=ticker,
            limit=limit,
            offset=offset,
        )
    items = [TransactionOut.model_validate(tx) for tx in transactions]
    return TransactionListResponse(total=total, limit=limit, offset=offset, items=items)


@app.delete(
    "/portfolios/{portfolio_id}/transactions/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete transaction",
)
async def delete_transaction(
    portfolio_id: UUID,
    transaction_id: UUID,
) -> Response:
    async with session_scope() as session:
        async with session.begin():
            try:
                await crud_transactions.delete_transaction(
                    session,
                    portfolio_id=portfolio_id,
                    transaction_id=transaction_id,
                )
            except TransactionNotFoundError:
                raise HTTPException(status_code=404, detail="Transaction not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(
    "/portfolios/{portfolio_id}/positions",
    response_model=List[PositionOut],
    summary="Current positions",
)
async def portfolio_positions(portfolio_id: UUID) -> List[PositionOut]:
    async with session_scope() as session:
        try:
            await crud_portfolios.get_portfolio(session, portfolio_id)
        except PortfolioNotFoundError:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        positions = await compute_positions(session, portfolio_id=portfolio_id)
    return positions


@app.get(
    "/portfolios/{portfolio_id}/metrics",
    response_model=PortfolioMetricsResponse,
    summary="Portfolio metrics",
)
async def portfolio_metrics(
    portfolio_id: UUID,
    start: date = Query(..., alias="from"),
    end: date = Query(..., alias="to"),
    rf: float = Query(0.0),
    mar: float = Query(0.0),
) -> PortfolioMetricsResponse:
    if start > end:
        raise HTTPException(status_code=400, detail="from must be on or before to")
    async with session_scope() as session:
        try:
            await crud_portfolios.get_portfolio(session, portfolio_id)
        except PortfolioNotFoundError:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        metrics = await compute_portfolio_metrics(
            session,
            portfolio_id=portfolio_id,
            start=start,
            end=end,
            rf=rf,
            mar=mar,
        )
    return metrics
