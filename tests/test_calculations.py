from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from backend.app.services.calculations.metrics import basic_metrics, advanced_metrics
from backend.app.services.calculations.signals import tech_signals


def _mock_history(closes: list[float], start: date) -> dict:
    data = []
    for idx, close in enumerate(closes):
        day = start + timedelta(days=idx)
        data.append({"date": day.isoformat(), "close": close})
    return {
        "ticker": "VOO",
        "start": start.isoformat(),
        "end": (start + timedelta(days=len(closes) - 1)).isoformat(),
        "interval": "1d",
        "count": len(closes),
        "data": data,
    }


@pytest.fixture
def mock_history(monkeypatch):
    def factory(closes: list[float], start: date):
        payload = _mock_history(closes, start)

        def _fake_get_history(*args, **kwargs):  # noqa: ANN001, ANN202
            return payload

        from backend.app.services.calculations import metrics as metrics_module
        from backend.app.services.calculations import signals as signals_module

        monkeypatch.setattr(metrics_module, "get_history", _fake_get_history)
        monkeypatch.setattr(signals_module, "get_history", _fake_get_history)
        return payload

    return factory


def test_basic_metrics(mock_history):
    closes = [100, 102, 101, 103, 104]
    start = date(2025, 1, 1)
    mock_history(closes, start)

    result = basic_metrics("VOO", start, start + timedelta(days=4), rf=0.01)
    assert result["ticker"] == "VOO"
    assert result["n"] == len(closes)
    assert result["ann_return"] is not None
    assert result["ann_volatility"] is not None
    rets = np.diff(closes) / np.array(closes[:-1])
    mean_daily = np.mean(rets)
    expected_ann_return = (1 + mean_daily) ** 252 - 1
    assert pytest.approx(result["ann_return"], rel=1e-3) == expected_ann_return


def test_advanced_metrics(mock_history):
    closes = [20, 21, 22, 23, 24, 25]
    start = date(2025, 3, 1)
    mock_history(closes, start)

    result = advanced_metrics("VOO", start, start + timedelta(days=5), rf=0.0, mar=0.0)
    assert result["calmar"] is None or result["calmar"] >= 0
    assert result["downside_volatility"] is not None
    assert result["ytd_return"] is not None


def test_tech_signals(mock_history):
    closes = [100 + i for i in range(80)]
    start = date(2025, 1, 1)
    mock_history(closes, start)

    result = tech_signals("VOO", start, start + timedelta(days=79), window=10, fast=5, slow=20, rsi_period=14)
    assert result["count"] == len(closes)
    assert result["momentum"] is not None
    assert result["sma_fast"] is not None
    assert result["sma_slow"] is not None
    assert result["rsi"] is None or isinstance(result["rsi"], float)

