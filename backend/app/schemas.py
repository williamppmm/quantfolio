# backend/app/schemas.py

from typing import Optional, List
from pydantic import BaseModel, Field

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
    low:  Optional[float] = Field(None, example=596.05)
    close: float = Field(..., example=599.64)
    volume: Optional[int] = Field(None, example=12345678)

class HistoryResponse(BaseModel):
    ticker: str = Field(..., example="VOO")
    interval: str = Field(..., pattern="^(1d|1wk|1mo)$", example="1d")
    start: str = Field(..., description="YYYY-MM-DD", example="2025-01-01")
    end: Optional[str] = Field(None, description="YYYY-MM-DD", example="2025-09-10")
    count: int = Field(..., example=170)
    data: List[Candle]

class BasicMetricsResponse(BaseModel):
    ticker: str = Field(..., example="VOO")
    start: str = Field(..., example="2025-01-01")
    end: Optional[str] = Field(None, example="2025-09-10")
    n: int = Field(..., example=170, description="Número de observaciones en el rango")
    ann_return: float = Field(..., example=0.12, description="Retorno anualizado (decimal)")
    ann_volatility: float = Field(..., example=0.17, description="Volatilidad anualizada (decimal)")
    sharpe: Optional[float] = Field(None, example=0.70, description="Sharpe ratio sobre rf")
    max_drawdown: float = Field(..., example=-0.09, description="Máximo drawdown (decimal)")
    rf: float = Field(..., example=0.02, description="Tasa libre de riesgo anual usada")

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
    last_cross_type: Optional[str] = Field(None, example="golden")  # o "death"

    rsi_period: int = Field(..., example=14)
    rsi: Optional[float] = Field(None, example=56.7)