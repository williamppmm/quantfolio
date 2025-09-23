from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException

from backend.app import main


def test_root_endpoint(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Portfolio Manager API running"}


def test_health_endpoint(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_last_price_endpoint(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "get_last_close",
        lambda ticker: {"ticker": ticker.upper(), "date": "2024-01-05", "close": 123.45},
    )

    response = client.get("/prices/spy/last")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "SPY"
    assert payload["close"] == pytest.approx(123.45)


def test_last_price_error(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_: str) -> None:
        raise HTTPException(status_code=502, detail="upstream")

    monkeypatch.setattr(main, "get_last_close", _raise)

    response = client.get("/prices/spy/last")
    assert response.status_code == 502
    assert response.json()["detail"] == "upstream"


def test_price_range_endpoint(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "get_history",
        lambda ticker, start, end, interval="1d": {
            "ticker": ticker.upper(),
            "interval": interval,
            "start": start.isoformat(),
            "end": end.isoformat() if end else None,
            "count": 2,
            "data": [
                {"date": start.isoformat(), "close": 100.0},
                {"date": (end or start).isoformat(), "close": 101.0},
            ],
        },
    )

    response = client.get("/prices/qqq/range", params={
        "start": "2024-01-01",
        "end": "2024-01-02",
        "interval": "1d",
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "QQQ"
    assert payload["count"] == 2


def test_price_range_invalid_interval(client) -> None:
    response = client.get("/prices/qqq/range", params={
        "start": "2024-01-01",
        "end": "2024-01-02",
        "interval": "5m",
    })

    assert response.status_code == 422


def test_price_range_error(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "get_history",
        lambda *_, **__: (_ for _ in ()).throw(HTTPException(status_code=404, detail="missing")),
    )

    response = client.get("/prices/iwm/range", params={"start": "2024-01-01", "end": "2024-01-02"})
    assert response.status_code == 404
    assert response.json()["detail"] == "missing"


def test_basic_metrics_endpoint(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "basic_metrics",
        lambda *_, **__: {
            "ticker": "DIA",
            "start": "2024-01-01",
            "end": "2024-01-10",
            "n": 10,
            "ann_return": 0.15,
            "ann_volatility": 0.2,
            "sharpe": 1.5,
            "max_drawdown": -0.1,
            "rf": 0.02,
        },
    )

    response = client.get(
        "/metrics/dia/basic",
        params={"start": "2024-01-01", "end": "2024-01-10", "rf": 0.02},
    )

    assert response.status_code == 200
    assert response.json()["ticker"] == "DIA"


def test_basic_metrics_error(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "basic_metrics",
        lambda *_, **__: (_ for _ in ()).throw(HTTPException(status_code=400, detail="bad range")),
    )

    response = client.get(
        "/metrics/dia/basic",
        params={"start": "2024-01-01", "end": "2024-01-10"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "bad range"


def test_advanced_metrics_endpoint(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "advanced_metrics",
        lambda *_, **__: {
            "ticker": "DIA",
            "start": "2024-01-01",
            "end": "2024-01-10",
            "n": 10,
            "ann_return": 0.12,
            "ann_volatility": 0.18,
            "sharpe": 1.2,
            "max_drawdown": -0.08,
            "rf": 0.01,
            "mar": 0.02,
            "downside_volatility": 0.05,
            "sortino": 1.0,
            "calmar": 1.5,
            "ytd_return": 0.04,
        },
    )

    response = client.get(
        "/metrics/dia/advanced",
        params={"start": "2024-01-01", "end": "2024-01-10", "rf": 0.01, "mar": 0.02},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "DIA"
    assert payload["mar"] == pytest.approx(0.02)


def test_signals_endpoint(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "tech_signals",
        lambda *_, **__: {
            "ticker": "DIA",
            "start": "2024-01-01",
            "end": "2024-01-10",
            "count": 10,
            "price": 400.0,
            "momentum_window": 3,
            "momentum": 0.05,
            "sma_fast_window": 2,
            "sma_fast": 390.0,
            "sma_slow_window": 3,
            "sma_slow": 385.0,
            "cross_now": True,
            "last_cross_date": "2024-01-09",
            "last_cross_type": "golden",
            "rsi_period": 14,
            "rsi": 55.0,
        },
    )

    response = client.get(
        "/signals/dia/tech",
        params={
            "start": "2024-01-01",
            "end": "2024-01-10",
            "window": 3,
            "fast": 2,
            "slow": 3,
            "rsi_period": 14,
        },
    )

    assert response.status_code == 200
    assert response.json()["cross_now"] is True


def test_signals_error(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "tech_signals",
        lambda *_, **__: (_ for _ in ()).throw(HTTPException(status_code=400, detail="bad window")),
    )

    response = client.get(
        "/signals/dia/tech",
        params={"start": "2024-01-01", "end": "2024-01-10"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "bad window"
