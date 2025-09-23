from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .errors import PortfolioAlreadyExistsError, PortfolioNotFoundError
from .models import Portfolio


async def create_portfolio(session: AsyncSession, *, name: str) -> Portfolio:
    normalized = name.strip()
    if not normalized:
        raise ValueError("Portfolio name cannot be empty")

    portfolio = Portfolio(name=normalized)
    session.add(portfolio)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise PortfolioAlreadyExistsError(normalized) from exc

    await session.refresh(portfolio)
    return portfolio


async def list_portfolios(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
    with_transactions: bool = False,
) -> Sequence[Portfolio]:
    stmt = select(Portfolio).order_by(Portfolio.created_at.asc()).limit(limit).offset(offset)
    if with_transactions:
        stmt = stmt.options(selectinload(Portfolio.transactions))
    result = await session.execute(stmt)
    return result.scalars().all()


async def count_portfolios(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(Portfolio))
    return int(result.scalar_one())


async def get_portfolio(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    *,
    with_transactions: bool = False,
) -> Portfolio:
    stmt = select(Portfolio).where(Portfolio.id == portfolio_id)
    if with_transactions:
        stmt = stmt.options(selectinload(Portfolio.transactions))
    result = await session.execute(stmt)
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise PortfolioNotFoundError(str(portfolio_id))
    return portfolio


async def delete_portfolio(session: AsyncSession, portfolio_id: uuid.UUID) -> None:
    portfolio = await get_portfolio(session, portfolio_id)
    await session.delete(portfolio)
