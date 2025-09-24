from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from fastapi import HTTPException

from backend.app.services.calculations import signals
from tests.helpers import make_history_payload


def test_rsi_returns_none_for_constant_series() -> None:
    series = pd.Series([10.0, 10.0, 10.0, 10.0])
    assert signals._rsi(series, period=3) is None


def test_tech_signals_success(monkeypatch: pytest.MonkeyPatch) -> None:
    closes = [10.0, 12.0, 11.0, 13.0, 12.5, 14.0]
    payload = make_history_payload(closes, ticker="TECH")
    monkeypatch.setattr(signals, "get_history", lambda *_, **__: payload)

    result = signals.tech_signals(
        "tech",
        date(2024, 1, 1),
        date(2024, 1, 6),
        window=3,
        fast=2,
        slow=3,
        rsi_period=3,
    )

    closes_series = pd.Series(closes, dtype=float)
    momentum = float(closes_series.pct_change(3).iloc[-1])
    sma_fast = float(closes_series.rolling(2).mean().iloc[-1])
    sma_slow = float(closes_series.rolling(3).mean().iloc[-1])
    cross_flag = (closes_series.rolling(2).mean() > closes_series.rolling(3).mean()).astype(int)
    cross_change = cross_flag.diff()
    valid_changes = cross_change.dropna()
    last_idx = valid_changes[valid_changes != 0].index[-1]
    last_cross_date = payload["data"][last_idx]["date"]
    last_cross_type = "golden" if cross_change.loc[last_idx] > 0 else "death"
    expected_rsi = signals._rsi(closes_series, 3)

    assert result["ticker"] == "TECH"
    assert result["count"] == len(closes)
    assert result["price"] == pytest.approx(closes[-1])
    assert result["momentum_window"] == 3
    assert result["momentum"] == pytest.approx(momentum)
    assert result["sma_fast_window"] == 2
    assert result["sma_fast"] == pytest.approx(sma_fast)
    assert result["sma_slow_window"] == 3
    assert result["sma_slow"] == pytest.approx(sma_slow)
    assert result["cross_now"] is True
    assert result["last_cross_date"] == last_cross_date
    assert result["last_cross_type"] == last_cross_type
    assert result["rsi_period"] == 3
    if expected_rsi is None:
        assert result["rsi"] is None
    else:
        assert result["rsi"] == pytest.approx(expected_rsi)


def test_tech_signals_requires_enough_history(monkeypatch: pytest.MonkeyPatch) -> None:
    closes = [10.0, 11.0, 12.0]
    payload = make_history_payload(closes, ticker="SHORT")
    monkeypatch.setattr(signals, "get_history", lambda *_, **__: payload)

    with pytest.raises(HTTPException) as exc:
        signals.tech_signals("short", date(2024, 1, 1), date(2024, 1, 3), window=3, slow=3)

    assert exc.value.status_code == 404


def test_tech_signals_requires_close_column(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = make_history_payload([10.0, 11.0, 12.0, 13.0], ticker="MISS")
    for record in payload["data"]:
        record.pop("close")
    monkeypatch.setattr(signals, "get_history", lambda *_, **__: payload)

    with pytest.raises(HTTPException) as exc:
        signals.tech_signals(
            "miss",
            date(2024, 1, 1),
            date(2024, 1, 4),
            window=2,
            fast=1,
            slow=2,
        )

    assert exc.value.status_code == 500


def test_tech_signals_rsi_none_with_short_series(monkeypatch: pytest.MonkeyPatch) -> None:
    closes = [10.0, 11.0, 12.0, 13.0]
    payload = make_history_payload(closes, ticker="RSI")
    monkeypatch.setattr(signals, "get_history", lambda *_, **__: payload)

    result = signals.tech_signals(
        "rsi",
        date(2024, 1, 1),
        date(2024, 1, 4),
        window=2,
        fast=2,
        slow=3,
        rsi_period=10,
    )

    assert result["rsi"] is None


def test_tech_signals_without_cross(monkeypatch: pytest.MonkeyPatch) -> None:
    closes = [10.0, 10.0, 10.0, 10.0]
    payload = make_history_payload(closes, ticker="FLAT")
    monkeypatch.setattr(signals, "get_history", lambda *_, **__: payload)

    result = signals.tech_signals(
        "flat",
        date(2024, 1, 1),
        date(2024, 1, 4),
        window=2,
        fast=2,
        slow=2,
        rsi_period=3,
    )

    assert result["last_cross_date"] is None
    assert result["last_cross_type"] is None
