from __future__ import annotations

from datetime import date

import pytest

from backend.app.db import crud_portfolios, crud_prices, crud_transactions
from backend.app.db.models import Price, TransactionType
from backend.app.services.portfolios import compute_portfolio_metrics, compute_positions


async def _seed_portfolio(session, name: str = "Test"):
    async with session.begin():
        portfolio = await crud_portfolios.create_portfolio(session, name=name)
    return portfolio


@pytest.mark.asyncio
async def test_compute_positions(db_session, monkeypatch):
    portfolio = await _seed_portfolio(db_session)
    trade_date = date(2025, 1, 1)

    async with db_session.begin():
        await crud_transactions.create_transaction(
            db_session,
            portfolio=portfolio,
            ticker="VOO",
            tx_type=TransactionType.BUY,
            tx_date=trade_date,
            quantity=10,
            price=100,
            amount=None,
        )
        db_session.add_all([
            Price(id=1, ticker="VOO", date=trade_date, open=100.0, high=100.0, low=100.0, close=100.0, volume=1000),
            Price(id=2, ticker="VOO", date=date(2025, 1, 2), open=102.0, high=106.0, low=101.0, close=105.0, volume=2000),
        ])

    async def _fake_latest(session, tickers):
        return {
            "VOO": Price(
                id=2,
                ticker="VOO",
                date=date(2025, 1, 2),
                open=102.0,
                high=106.0,
                low=101.0,
                close=105.0,
                volume=2000,
            )
        }

    from backend.app.services import portfolios as portfolios_service
    monkeypatch.setattr(portfolios_service, "get_latest_prices_for", _fake_latest)

    positions = await compute_positions(db_session, portfolio_id=portfolio.id)
    assert len(positions) == 1
    position = positions[0]
    assert position.ticker == "VOO"
    assert float(position.quantity) == pytest.approx(10.0)
    assert float(position.avg_cost) == pytest.approx(100.0, rel=1e-3)
    assert float(position.market_price) == pytest.approx(105.0, rel=1e-3)
    assert float(position.market_value) == pytest.approx(1050.0, rel=1e-3)
    assert float(position.unrealized_pnl) == pytest.approx(50.0, rel=1e-3)


@pytest.mark.asyncio
async def test_compute_portfolio_metrics(db_session):
    portfolio = await _seed_portfolio(db_session, name="Metrics")
    start = date(2025, 1, 1)
    end = date(2025, 1, 3)

    async with db_session.begin():
        await crud_transactions.create_transaction(
            db_session,
            portfolio=portfolio,
            ticker="VOO",
            tx_type=TransactionType.BUY,
            tx_date=start,
            quantity=5,
            price=100,
            amount=None,
        )
        db_session.add_all([
            Price(id=3, ticker="VOO", date=start, open=100.0, high=100.0, low=100.0, close=100.0, volume=1000),
            Price(id=4, ticker="VOO", date=date(2025, 1, 2), open=100.0, high=110.0, low=99.0, close=110.0, volume=1500),
            Price(id=5, ticker="VOO", date=end, open=110.0, high=120.0, low=108.0, close=120.0, volume=2000),
        ])

    metrics = await compute_portfolio_metrics(
        db_session,
        portfolio_id=portfolio.id,
        start=start,
        end=end,
        rf=0.0,
        mar=0.0,
    )
    assert metrics.portfolio_id == portfolio.id
    assert metrics.tickers == ["VOO"]
    assert metrics.n_days >= 1
    assert metrics.ann_return is not None and metrics.ann_return > 0
    assert metrics.ann_volatility is not None and metrics.ann_volatility >= 0
    assert metrics.max_drawdown <= 0

