from __future__ import annotations

from datetime import date

import pytest

from backend.app.db.models import Price


@pytest.mark.asyncio
async def test_health_and_portfolio_flow(client, db_session):
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    create_resp = await client.post("/portfolios", json={"name": "API"})
    assert create_resp.status_code == 201
    portfolio_id = create_resp.json()["id"]

    trade_date = date(2025, 2, 1)
    async with db_session.begin():
        db_session.add_all([
            Price(
                id=1,
                ticker="VOO",
                date=trade_date,
                open=100.0,
                high=102.0,
                low=99.0,
                close=100.0,
                volume=1000,
            ),
            Price(
                id=2,
                ticker="VOO",
                date=date(2025, 2, 2),
                open=101.0,
                high=105.0,
                low=100.0,
                close=104.0,
                volume=1200,
            ),
        ])

    last_price_resp = await client.get("/prices/VOO/db/last")
    assert last_price_resp.status_code == 200

    range_resp = await client.get(
        "/prices/VOO/db/range",
        params={"start": trade_date.isoformat(), "end": date(2025, 2, 2).isoformat()},
    )
    assert range_resp.status_code == 200
    assert range_resp.json()["total"] == 2

    tx_resp = await client.post(
        f"/portfolios/{portfolio_id}/transactions",
        json={
            "ticker": "VOO",
            "date": trade_date.isoformat(),
            "type": "BUY",
            "quantity": 3,
            "price": 100,
        },
    )
    assert tx_resp.status_code == 201
    transaction_id = tx_resp.json()["id"]

    list_resp = await client.get(f"/portfolios/{portfolio_id}/transactions")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    positions_resp = await client.get(f"/portfolios/{portfolio_id}/positions")
    assert positions_resp.status_code == 200
    positions = positions_resp.json()
    assert len(positions) == 1 and positions[0]["ticker"] == "VOO"

    metrics_resp = await client.get(
        f"/portfolios/{portfolio_id}/metrics",
        params={"from": trade_date.isoformat(), "to": date(2025, 2, 2).isoformat()},
    )
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert metrics["portfolio_id"] == portfolio_id
    assert metrics["tickers"] == ["VOO"]

    delete_tx = await client.delete(
        f"/portfolios/{portfolio_id}/transactions/{transaction_id}"
    )
    assert delete_tx.status_code == 204

    delete_portfolio_resp = await client.delete(f"/portfolios/{portfolio_id}")
    assert delete_portfolio_resp.status_code == 204
