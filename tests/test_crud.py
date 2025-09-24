from datetime import date
import uuid

import pytest

from backend.app.db import crud_portfolios, crud_transactions
from backend.app.db.errors import PortfolioAlreadyExistsError, PortfolioNotFoundError, InvalidTransactionError
from backend.app.db.models import TransactionType


@pytest.mark.asyncio
async def test_create_and_get_portfolio(db_session):
    async with db_session.begin():
        portfolio = await crud_portfolios.create_portfolio(db_session, name="Core")
    fetched = await crud_portfolios.get_portfolio(db_session, portfolio.id)
    assert fetched.id == portfolio.id
    assert fetched.name == "Core"

    await db_session.rollback()

    with pytest.raises(PortfolioAlreadyExistsError):
        async with db_session.begin():
            await crud_portfolios.create_portfolio(db_session, name="Core")


@pytest.mark.asyncio
async def test_transaction_validation(db_session):
    async with db_session.begin():
        portfolio = await crud_portfolios.create_portfolio(db_session, name="Alpha")

    with pytest.raises(InvalidTransactionError):
        async with db_session.begin():
            await crud_transactions.create_transaction(
                db_session,
                portfolio=portfolio,
                ticker="VOO",
                tx_type=TransactionType.BUY,
                tx_date=date(2024, 1, 1),
                quantity=None,
                price=100,
                amount=None,
            )


@pytest.mark.asyncio
async def test_aggregate_positions(db_session):
    async with db_session.begin():
        portfolio = await crud_portfolios.create_portfolio(db_session, name="Positions")

    async with db_session.begin():
        await crud_transactions.create_transaction(
            db_session,
            portfolio=portfolio,
            ticker="VOO",
            tx_type=TransactionType.BUY,
            tx_date=date(2024, 1, 1),
            quantity=10,
            price=100,
            amount=None,
        )
        await crud_transactions.create_transaction(
            db_session,
            portfolio=portfolio,
            ticker="VOO",
            tx_type=TransactionType.SELL,
            tx_date=date(2024, 1, 1),
            quantity=2,
            price=110,
            amount=None,
        )

    result = await crud_transactions.aggregate_positions(db_session, portfolio_id=portfolio.id)
    assert len(result) == 1
    aggregated = result[0]
    assert aggregated["ticker"] == "VOO"
    assert float(aggregated["quantity"]) == pytest.approx(8.0)
    # cost = 10*100 - 2*110 = 780
    assert float(aggregated["cost"]) == pytest.approx(780.0)





@pytest.mark.asyncio
async def test_list_and_delete_transactions(db_session):
    async with db_session.begin():
        portfolio = await crud_portfolios.create_portfolio(db_session, name="Lister")

    tx_date = date(2024, 1, 1)
    async with db_session.begin():
        tx1 = await crud_transactions.create_transaction(
            db_session,
            portfolio=portfolio,
            ticker="VOO",
            tx_type=TransactionType.BUY,
            tx_date=tx_date,
            quantity=5,
            price=100,
            amount=None,
        )
        await crud_transactions.create_transaction(
            db_session,
            portfolio=portfolio,
            ticker="VOO",
            tx_type=TransactionType.SELL,
            tx_date=tx_date,
            quantity=2,
            price=110,
            amount=None,
        )

    count = await crud_transactions.count_transactions(db_session, portfolio_id=portfolio.id)
    assert count == 2

    items = await crud_transactions.list_transactions(db_session, portfolio_id=portfolio.id)
    assert len(items) == 2

    await db_session.rollback()

    async with db_session.begin():
        await crud_transactions.delete_transaction(
            db_session,
            portfolio_id=portfolio.id,
            transaction_id=tx1.id,
        )

    await db_session.rollback()

    remaining = await crud_transactions.count_transactions(db_session, portfolio_id=portfolio.id)
    assert remaining == 1




@pytest.mark.asyncio
async def test_create_portfolio_invalid_name(db_session):
    with pytest.raises(ValueError):
        async with db_session.begin():
            await crud_portfolios.create_portfolio(db_session, name="   ")


@pytest.mark.asyncio
async def test_get_portfolio_not_found(db_session):
    with pytest.raises(PortfolioNotFoundError):
        await crud_portfolios.get_portfolio(db_session, uuid.uuid4())


@pytest.mark.asyncio
async def test_portfolio_listing_with_filters(db_session):
    tx_date = date(2024, 2, 1)
    async with db_session.begin():
        portfolio = await crud_portfolios.create_portfolio(db_session, name="Coverage")
        await crud_transactions.create_transaction(
            db_session,
            portfolio=portfolio,
            ticker="VOO",
            tx_type=TransactionType.BUY,
            tx_date=tx_date,
            quantity=1,
            price=100,
            amount=None,
        )

    total = await crud_portfolios.count_portfolios(db_session)
    assert total == 1

    items = await crud_portfolios.list_portfolios(db_session, with_transactions=True)
    assert len(items) == 1
    assert len(items[0].transactions) == 1

    filtered_count = await crud_transactions.count_transactions(
        db_session,
        portfolio_id=portfolio.id,
        start=tx_date,
        end=tx_date,
        ticker="VOO",
    )
    assert filtered_count == 1

    filtered_transactions = await crud_transactions.list_transactions(
        db_session,
        portfolio_id=portfolio.id,
        start=tx_date,
        end=tx_date,
        ticker="VOO",
    )
    assert len(filtered_transactions) == 1

    await db_session.rollback()

    async with db_session.begin():
        await crud_portfolios.delete_portfolio(db_session, portfolio_id=portfolio.id)

    assert await crud_portfolios.count_portfolios(db_session) == 0
