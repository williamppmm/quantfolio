from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Sequence

import sqlalchemy as sa
from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .errors import InvalidTransactionError, TransactionNotFoundError
from .models import Portfolio, Transaction, TransactionType

_DECIMAL_QUANT = Decimal("0.00000001")


def _to_decimal(value: Decimal | float | int | str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value.quantize(_DECIMAL_QUANT)
    try:
        return Decimal(str(value)).quantize(_DECIMAL_QUANT)
    except (InvalidOperation, ValueError) as exc:
        raise InvalidTransactionError(f"Invalid decimal value: {value}") from exc


def _normalize_ticker(ticker: str) -> str:
    if not ticker or not ticker.strip():
        raise InvalidTransactionError("Ticker is required")
    return ticker.strip().upper()


def _resolve_type(value: TransactionType | str) -> TransactionType:
    if isinstance(value, TransactionType):
        return value
    try:
        return TransactionType(value.upper())
    except ValueError as exc:
        allowed = ", ".join(member.value for member in TransactionType)
        raise InvalidTransactionError(f"Unsupported transaction type. Allowed: {allowed}") from exc


def _validate_payload(
    *,
    tx_type: TransactionType,
    quantity: Decimal | None,
    price: Decimal | None,
    amount: Decimal | None,
    tx_date: date,
) -> None:
    if tx_date > date.today():
        raise InvalidTransactionError("Transaction date cannot be in the future")

    if tx_type in {TransactionType.BUY, TransactionType.SELL}:
        if quantity is None or quantity <= 0:
            raise InvalidTransactionError("Quantity must be > 0 for BUY/SELL")
        if price is None or price < 0:
            raise InvalidTransactionError("Price must be >= 0 for BUY/SELL")
    else:
        if amount is None or amount < 0:
            raise InvalidTransactionError("Amount must be >= 0 for DIVIDEND/FEE")


def _base_select(portfolio_id: uuid.UUID) -> Select[tuple[Transaction]]:
    return select(Transaction).where(Transaction.portfolio_id == portfolio_id)


async def create_transaction(
    session: AsyncSession,
    *,
    portfolio: Portfolio,
    ticker: str,
    tx_type: TransactionType | str,
    tx_date: date,
    quantity: Decimal | float | int | str | None,
    price: Decimal | float | int | str | None,
    amount: Decimal | float | int | str | None,
) -> Transaction:
    normalized_type = _resolve_type(tx_type)
    normalized_ticker = _normalize_ticker(ticker)
    quantity_dec = _to_decimal(quantity)
    price_dec = _to_decimal(price)
    amount_dec = _to_decimal(amount)

    _validate_payload(
        tx_type=normalized_type,
        quantity=quantity_dec,
        price=price_dec,
        amount=amount_dec,
        tx_date=tx_date,
    )

    transaction = Transaction(
        portfolio_id=portfolio.id,
        ticker=normalized_ticker,
        date=tx_date,
        type=normalized_type,
        quantity=quantity_dec,
        price=price_dec,
        amount=amount_dec,
    )

    session.add(transaction)
    try:
        await session.flush()
    except Exception as exc:
        raise InvalidTransactionError("Transaction violates database constraints") from exc

    await session.refresh(transaction)
    session.expunge(transaction)
    return transaction


async def list_transactions(
    session: AsyncSession,
    *,
    portfolio_id: uuid.UUID,
    start: date | None = None,
    end: date | None = None,
    ticker: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Transaction]:
    stmt = _base_select(portfolio_id)
    if start is not None:
        stmt = stmt.where(Transaction.date >= start)
    if end is not None:
        stmt = stmt.where(Transaction.date <= end)
    if ticker:
        stmt = stmt.where(Transaction.ticker == _normalize_ticker(ticker))

    stmt = stmt.order_by(Transaction.date.asc(), Transaction.created_at.asc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return result.scalars().all()


async def count_transactions(
    session: AsyncSession,
    *,
    portfolio_id: uuid.UUID,
    start: date | None = None,
    end: date | None = None,
    ticker: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(Transaction).where(Transaction.portfolio_id == portfolio_id)
    if start is not None:
        stmt = stmt.where(Transaction.date >= start)
    if end is not None:
        stmt = stmt.where(Transaction.date <= end)
    if ticker:
        stmt = stmt.where(Transaction.ticker == _normalize_ticker(ticker))
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def get_transaction(
    session: AsyncSession,
    *,
    portfolio_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> Transaction:
    stmt = _base_select(portfolio_id).where(Transaction.id == transaction_id)
    result = await session.execute(stmt)
    transaction = result.scalar_one_or_none()
    if transaction is None:
        raise TransactionNotFoundError(str(transaction_id))
    return transaction


async def delete_transaction(
    session: AsyncSession,
    *,
    portfolio_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> None:
    transaction = await get_transaction(session, portfolio_id=portfolio_id, transaction_id=transaction_id)
    await session.delete(transaction)


async def get_all_transactions(
    session: AsyncSession,
    *,
    portfolio_id: uuid.UUID,
    up_to: date | None = None,
) -> Sequence[Transaction]:
    stmt = _base_select(portfolio_id)
    if up_to is not None:
        stmt = stmt.where(Transaction.date <= up_to)
    stmt = stmt.order_by(Transaction.date.asc(), Transaction.created_at.asc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def aggregate_positions(session: AsyncSession, *, portfolio_id: uuid.UUID) -> Sequence[dict]:
    qty_case = case(
        (Transaction.type == TransactionType.BUY, Transaction.quantity),
        (Transaction.type == TransactionType.SELL, -Transaction.quantity),
        else_=sa.literal(0, type_=sa.Numeric(24, 8)),
    )
    cost_case = case(
        (Transaction.type == TransactionType.BUY, Transaction.quantity * Transaction.price),
        (Transaction.type == TransactionType.SELL, -Transaction.quantity * Transaction.price),
        else_=sa.literal(0, type_=sa.Numeric(24, 8)),
    )

    stmt = (
        select(
            Transaction.ticker,
            func.coalesce(func.sum(qty_case), Decimal(0)).label("quantity"),
            func.coalesce(func.sum(cost_case), Decimal(0)).label("cost"),
        )
        .where(Transaction.portfolio_id == portfolio_id)
        .group_by(Transaction.ticker)
        .order_by(Transaction.ticker.asc())
    )
    result = await session.execute(stmt)
    return [dict(row._mapping) for row in result]
