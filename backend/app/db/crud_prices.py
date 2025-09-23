from datetime import date as dt_date
from decimal import Decimal
from typing import Dict, Iterable, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Price


def _to_decimal(value):
    if value is None:
        return None
    return Decimal(str(round(float(value), 6)))


def _to_date(value):
    if value is None:
        return None
    if isinstance(value, dt_date):
        return value
    return dt_date.fromisoformat(str(value))


async def upsert_prices(
    session: AsyncSession,
    ticker: str,
    rows: Iterable[dict],
) -> int:
    ticker = ticker.upper()
    payload = []
    for row in rows:
        payload.append(
            {
                "ticker": ticker,
                "date": _to_date(row.get("date")),
                "open": _to_decimal(row.get("open")),
                "high": _to_decimal(row.get("high")),
                "low": _to_decimal(row.get("low")),
                "close": _to_decimal(row.get("close")),
                "volume": int(row["volume"]) if row.get("volume") not in (None, "") else None,
            }
        )

    if not payload:
        return 0

    stmt = insert(Price).values(payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker", "date"],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
        },
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def read_prices_range(
    session: AsyncSession,
    ticker: str,
    start: dt_date,
    end: dt_date | None,
) -> Sequence[Price]:
    stmt = select(Price).where(Price.ticker == ticker.upper(), Price.date >= start)
    if end is not None:
        stmt = stmt.where(Price.date <= end)
    stmt = stmt.order_by(Price.date.asc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_last_date(session: AsyncSession, ticker: str) -> dt_date | None:
    stmt = select(func.max(Price.date)).where(Price.ticker == ticker.upper())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def count_prices_range(
    session: AsyncSession,
    ticker: str,
    start: dt_date,
    end: dt_date | None,
) -> int:
    stmt = select(func.count()).select_from(Price).where(Price.ticker == ticker.upper(), Price.date >= start)
    if end is not None:
        stmt = stmt.where(Price.date <= end)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def read_prices_range_paged(
    session: AsyncSession,
    ticker: str,
    start: dt_date,
    end: dt_date | None,
    limit: int = 200,
    offset: int = 0,
) -> Sequence[Price]:
    stmt = select(Price).where(Price.ticker == ticker.upper(), Price.date >= start)
    if end is not None:
        stmt = stmt.where(Price.date <= end)
    stmt = stmt.order_by(Price.date.asc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_last_price(session: AsyncSession, ticker: str) -> Price | None:
    stmt = (
        select(Price)
        .where(Price.ticker == ticker.upper())
        .order_by(Price.date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_latest_prices_for(session: AsyncSession, tickers: Sequence[str]) -> Dict[str, Price]:
    normalized = sorted({ticker.upper() for ticker in tickers if ticker})
    if not normalized:
        return {}

    stmt: Select[tuple[Price]] = (
        select(Price)
        .where(Price.ticker.in_(normalized))
        .order_by(Price.ticker.asc(), Price.date.desc())
        .distinct(Price.ticker)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return {row.ticker: row for row in rows}


async def load_price_history_for_tickers(
    session: AsyncSession,
    tickers: Sequence[str],
    start: dt_date,
    end: dt_date | None,
) -> Dict[str, list[Price]]:
    normalized = sorted({ticker.upper() for ticker in tickers if ticker})
    if not normalized:
        return {}

    stmt = select(Price).where(Price.ticker.in_(normalized), Price.date >= start)
    if end is not None:
        stmt = stmt.where(Price.date <= end)
    stmt = stmt.order_by(Price.ticker.asc(), Price.date.asc())

    result = await session.execute(stmt)
    data: Dict[str, list[Price]] = {ticker: [] for ticker in normalized}
    for price in result.scalars():
        data.setdefault(price.ticker, []).append(price)
    return data
