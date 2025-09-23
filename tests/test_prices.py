from __future__ import annotations

from datetime import date

import pytest

from backend.app.db import crud_prices
from backend.app.db.models import Price


@pytest.mark.asyncio
async def test_price_queries(db_session):
    async with db_session.begin():
        db_session.add_all([
            Price(id=10, ticker="VOO", date=date(2025, 1, 1), open=100.0, high=101.0, low=99.0, close=100.5, volume=1000),
            Price(id=11, ticker="VOO", date=date(2025, 1, 2), open=101.0, high=105.0, low=100.0, close=104.0, volume=1200),
            Price(id=12, ticker="SPY", date=date(2025, 1, 1), open=400.0, high=402.0, low=398.0, close=401.0, volume=2000),
        ])

    last = await crud_prices.get_last_price(db_session, "VOO")
    assert last is not None and float(last.close) == 104.0

    count = await crud_prices.count_prices_range(db_session, "VOO", date(2025, 1, 1), date(2025, 1, 2))
    assert count == 2

    rows = await crud_prices.read_prices_range(db_session, "VOO", date(2025, 1, 1), date(2025, 1, 2))
    assert len(rows) == 2

    latest = await crud_prices.get_latest_prices_for(db_session, ["VOO", "SPY"])
    assert set(latest.keys()) == {"VOO", "SPY"}
    assert float(latest["SPY"].close) == 401.0

    history = await crud_prices.load_price_history_for_tickers(db_session, ["VOO"], date(2025, 1, 1), date(2025, 1, 2))
    assert "VOO" in history and len(history["VOO"]) == 2
