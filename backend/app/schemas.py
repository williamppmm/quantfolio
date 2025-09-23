from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .db.models import TransactionType


class MessageResponse(BaseModel):
    message: str = Field(..., example="Portfolio Manager API running")


class HealthResponse(BaseModel):
    status: str = Field(..., example="ok")


class LastPriceResponse(BaseModel):
    ticker: str = Field(..., example="VOO")
    date: str = Field(..., description="YYYY-MM-DD", example="2025-09-10")
    close: float = Field(..., example=599.64)


class Candle(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD", example="2025-09-10")
    open: Optional[float] = Field(None, example=598.12)
    high: Optional[float] = Field(None, example=602.37)
    low: Optional[float] = Field(None, example=596.05)
    close: float = Field(..., example=599.64)
    volume: Optional[int] = Field(None, example=12345678)


class HistoryResponse(BaseModel):
    ticker: str = Field(..., example="VOO")
    interval: str = Field(..., pattern="^(1d|1wk|1mo)$", example="1d")
    start: str = Field(..., description="YYYY-MM-DD", example="2025-01-01")
    end: Optional[str] = Field(None, description="YYYY-MM-DD", example="2025-09-10")
    count: int = Field(..., example=170)
    data: List[Candle]

    total: Optional[int] = Field(None, description="Total rows for the query")
    limit: Optional[int] = Field(None, description="Pagination limit applied")
    offset: Optional[int] = Field(None, description="Pagination offset applied")


class BasicMetricsResponse(BaseModel):
    ticker: str = Field(..., example="VOO")
    start: str = Field(..., example="2025-01-01")
    end: Optional[str] = Field(None, example="2025-09-10")
    n: int = Field(..., example=170, description="Number of observations in the range")
    ann_return: float = Field(..., example=0.12, description="Annualized return (decimal)")
    ann_volatility: float = Field(..., example=0.17, description="Annualized volatility (decimal)")
    sharpe: Optional[float] = Field(None, example=0.70, description="Sharpe ratio over rf")
    max_drawdown: float = Field(..., example=-0.09, description="Maximum drawdown (decimal)")
    rf: float = Field(..., example=0.02, description="Risk-free rate used")


class AdvancedMetricsResponse(BaseModel):
    ticker: str
    start: str
    end: Optional[str]
    n: int
    ann_return: Optional[float]
    ann_volatility: Optional[float]
    sharpe: Optional[float]
    max_drawdown: Optional[float]
    rf: float
    mar: float
    downside_volatility: Optional[float]
    sortino: Optional[float]
    calmar: Optional[float]
    ytd_return: Optional[float]


class TechSignalsResponse(BaseModel):
    ticker: str = Field(..., example="VOO")
    start: str = Field(..., example="2025-01-01")
    end: Optional[str] = Field(None, example="2025-09-10")
    count: int = Field(..., example=171)
    price: Optional[float] = Field(None, example=599.64)

    momentum_window: int = Field(..., example=60)
    momentum: Optional[float] = Field(None, example=0.065)

    sma_fast_window: int = Field(..., example=20)
    sma_fast: Optional[float] = Field(None, example=585.12)

    sma_slow_window: int = Field(..., example=50)
    sma_slow: Optional[float] = Field(None, example=570.45)

    cross_now: bool = Field(..., example=True)
    last_cross_date: Optional[str] = Field(None, example="2025-03-12")
    last_cross_type: Optional[str] = Field(None, example="golden")

    rsi_period: int = Field(..., example=14)
    rsi: Optional[float] = Field(None, example=56.7)


class LastDbPriceResponse(BaseModel):
    ticker: str = Field(..., example="VOO")
    date: dt.date = Field(..., example="2025-09-10")
    close: Decimal = Field(..., example=Decimal("599.64"))
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    volume: Optional[int] = None


class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, example="Core Portfolio")

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class PortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: dt.datetime


class PortfolioListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[PortfolioOut]


class TransactionCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16, example="VOO")
    date: dt.date = Field(..., example="2025-01-02")
    type: TransactionType = Field(..., example=TransactionType.BUY)
    quantity: Optional[Decimal] = Field(None, gt=0)
    price: Optional[Decimal] = Field(None, ge=0)
    amount: Optional[Decimal] = Field(None, ge=0)

    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker cannot be empty")
        return normalized

    @field_validator("type", mode="before")
    @classmethod
    def parse_type(cls, value) -> TransactionType:
        if isinstance(value, TransactionType):
            return value
        try:
            return TransactionType(str(value).upper())
        except ValueError as exc:
            allowed = ", ".join(member.value for member in TransactionType)
            raise ValueError(f"type must be one of: {allowed}") from exc

    @field_validator("date")
    @classmethod
    def no_future_date(cls, value: dt.date) -> dt.date:
        if value > dt.date.today():
            raise ValueError("date cannot be in the future")
        return value

    @model_validator(mode="after")
    def validate_by_type(self) -> "TransactionCreate":
        if self.type in {TransactionType.BUY, TransactionType.SELL}:
            if self.quantity is None:
                raise ValueError("quantity is required for BUY/SELL")
            if self.price is None:
                raise ValueError("price is required for BUY/SELL")
        elif self.type in {TransactionType.DIVIDEND, TransactionType.FEE}:
            if self.amount is None:
                raise ValueError("amount is required for DIVIDEND/FEE")
        return self


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    ticker: str
    date: dt.date
    type: TransactionType
    quantity: Optional[Decimal]
    price: Optional[Decimal]
    amount: Optional[Decimal]
    created_at: dt.datetime


class TransactionListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[TransactionOut]


class PositionOut(BaseModel):
    ticker: str
    quantity: Decimal
    avg_cost: Optional[Decimal]
    market_price: Optional[Decimal]
    market_value: Decimal
    unrealized_pnl: Decimal


class PortfolioMetricsResponse(BaseModel):
    portfolio_id: UUID
    start: dt.date
    end: dt.date
    n_days: int
    tickers: List[str]
    ann_return: Optional[float]
    ann_volatility: Optional[float]
    sharpe: Optional[float]
    sortino: Optional[float]
    calmar: Optional[float]
    max_drawdown: Optional[float]
    downside_volatility: Optional[float]
    rf: float
    mar: float
