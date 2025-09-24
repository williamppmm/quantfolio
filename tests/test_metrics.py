from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException

from backend.app.services.calculations import metrics
from tests.helpers import make_history_payload


def _expected_basic_metrics(closes: list[float], rf: float) -> dict[str, float | None]:
    df = pd.DataFrame({"close": closes})
    df["ret"] = df["close"].pct_change()
    rets = df["ret"].dropna()
    mean_daily = float(rets.mean())
    std_daily = float(rets.std(ddof=1))
    ann_return = float((1 + mean_daily) ** metrics.TRADING_DAYS - 1)
    ann_vol = float(std_daily * np.sqrt(metrics.TRADING_DAYS))

    if rf:
        rf_daily = (1 + rf) ** (1 / metrics.TRADING_DAYS) - 1
    else:
        rf_daily = 0.0
    ann_excess = float((rets - rf_daily).mean() * metrics.TRADING_DAYS)
    sharpe = float(ann_excess / ann_vol) if ann_vol > 0 else None

    equity = (1 + rets).cumprod()
    peak = equity.cummax()
    drawdown = (equity / peak) - 1.0
    max_dd = float(drawdown.min())

    return {
        "ann_return": ann_return,
        "ann_volatility": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
    }


def _expected_advanced_metrics(closes: list[float], rf: float, mar: float) -> dict[str, float | None]:
    df = pd.DataFrame({"close": closes})
    df["ret"] = df["close"].pct_change()
    rets = df["ret"].dropna()
    mean_daily = float(rets.mean())
    std_daily = float(rets.std(ddof=1))
    ann_return = float((1 + mean_daily) ** metrics.TRADING_DAYS - 1)
    ann_vol = float(std_daily * np.sqrt(metrics.TRADING_DAYS))

    if rf:
        rf_daily = (1 + rf) ** (1 / metrics.TRADING_DAYS) - 1
    else:
        rf_daily = 0.0
    ann_excess = float((rets - rf_daily).mean() * metrics.TRADING_DAYS)
    sharpe = float(ann_excess / ann_vol) if ann_vol > 0 else None

    equity = (1 + rets).cumprod()
    peak = equity.cummax()
    drawdown = (equity / peak) - 1.0
    max_dd = float(drawdown.min())

    if mar:
        mar_daily = (1 + mar) ** (1 / metrics.TRADING_DAYS) - 1
    else:
        mar_daily = 0.0
    downside = rets[rets < mar_daily]
    if downside.empty:
        downside_vol_ann = None
        sortino = None
    else:
        downside_vol_daily = float(downside.std(ddof=1))
        downside_vol_ann = float(downside_vol_daily * np.sqrt(metrics.TRADING_DAYS))
        sortino = float((ann_return - mar) / downside_vol_ann) if downside_vol_ann > 0 else None

    calmar = float(ann_return / abs(max_dd)) if max_dd < 0 else None
    ytd_return = float(closes[-1] / closes[0] - 1.0)

    return {
        "ann_return": ann_return,
        "ann_volatility": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "downside_volatility": downside_vol_ann,
        "sortino": sortino,
        "calmar": calmar,
        "ytd_return": ytd_return,
    }


def test_basic_metrics_success(monkeypatch: pytest.MonkeyPatch) -> None:
    closes = [100.0, 102.0, 101.0, 103.0, 102.0]
    payload = make_history_payload(closes, ticker="VOO")
    monkeypatch.setattr(metrics, "get_history", lambda *_, **__: payload)

    result = metrics.basic_metrics("voo", date(2024, 1, 1), date(2024, 1, 5), rf=0.01)
    expected = _expected_basic_metrics(closes, rf=0.01)

    assert result["ticker"] == "VOO"
    assert result["n"] == len(closes)
    assert result["rf"] == pytest.approx(0.01)
    for key, value in expected.items():
        assert result[key] == pytest.approx(value, rel=5e-6, abs=1e-6)


def test_basic_metrics_zero_rf_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    closes = [100.0, 101.0, 102.0]
    payload = make_history_payload(closes, ticker="ZERO")
    monkeypatch.setattr(metrics, "get_history", lambda *_, **__: payload)

    result = metrics.basic_metrics("zero", date(2024, 1, 1), date(2024, 1, 3), rf=0.0)
    expected = _expected_basic_metrics(closes, rf=0.0)

    assert result["rf"] == pytest.approx(0.0)
    for key, value in expected.items():
        assert result[key] == pytest.approx(value, rel=5e-6, abs=1e-6)


def test_basic_metrics_requires_two_points(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = make_history_payload([150.0], ticker="ONE")
    monkeypatch.setattr(metrics, "get_history", lambda *_, **__: payload)

    with pytest.raises(HTTPException) as exc:
        metrics.basic_metrics("one", date(2024, 1, 1), date(2024, 1, 1))

    assert exc.value.status_code == 404


def test_basic_metrics_requires_close_column(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = make_history_payload([100.0, 101.0], ticker="MISS")
    for record in payload["data"]:
        record.pop("close")
    monkeypatch.setattr(metrics, "get_history", lambda *_, **__: payload)

    with pytest.raises(HTTPException) as exc:
        metrics.basic_metrics("miss", date(2024, 1, 1), date(2024, 1, 2))

    assert exc.value.status_code == 500


def test_basic_metrics_handles_empty_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = make_history_payload([None, 100.0], ticker="NA")
    monkeypatch.setattr(metrics, "get_history", lambda *_, **__: payload)

    with pytest.raises(HTTPException) as exc:
        metrics.basic_metrics("na", date(2024, 1, 1), date(2024, 1, 3))

    assert exc.value.status_code == 404


def test_advanced_metrics_success(monkeypatch: pytest.MonkeyPatch) -> None:
    closes = [100.0, 102.0, 101.0, 100.0, 103.0]
    payload = make_history_payload(closes, ticker="ADV")
    monkeypatch.setattr(metrics, "get_history", lambda *_, **__: payload)

    result = metrics.advanced_metrics("adv", date(2024, 1, 1), date(2024, 1, 5), rf=0.01, mar=0.0)
    expected = _expected_advanced_metrics(closes, rf=0.01, mar=0.0)

    assert result["ticker"] == "ADV"
    assert result["n"] == len(closes)
    assert result["rf"] == pytest.approx(0.01)
    assert result["mar"] == pytest.approx(0.0)
    for key, value in expected.items():
        if value is None or (isinstance(value, float) and np.isnan(value)):
            if key in result and result[key] is not None:
                assert result[key] == pytest.approx(value, rel=5e-6, abs=1e-6)
            else:
                assert result[key] is None or (isinstance(result[key], float) and np.isnan(result[key]))
        else:
            assert result[key] == pytest.approx(value, rel=5e-6, abs=1e-6)


def test_advanced_metrics_requires_two_points(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = make_history_payload([200.0], ticker="SHORT")
    monkeypatch.setattr(metrics, "get_history", lambda *_, **__: payload)

    with pytest.raises(HTTPException) as exc:
        metrics.advanced_metrics("short", date(2024, 1, 1), date(2024, 1, 1))

    assert exc.value.status_code == 404


def test_advanced_metrics_requires_close_column(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = make_history_payload([120.0, 121.0], ticker="MISSING")
    for record in payload["data"]:
        record.pop("close")
    monkeypatch.setattr(metrics, "get_history", lambda *_, **__: payload)

    with pytest.raises(HTTPException) as exc:
        metrics.advanced_metrics("missing", date(2024, 1, 1), date(2024, 1, 2))

    assert exc.value.status_code == 500


def test_advanced_metrics_handles_empty_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = make_history_payload([None, 100.0], ticker="VOID")
    monkeypatch.setattr(metrics, "get_history", lambda *_, **__: payload)

    with pytest.raises(HTTPException) as exc:
        metrics.advanced_metrics("void", date(2024, 1, 1), date(2024, 1, 3))

    assert exc.value.status_code == 404


def test_advanced_metrics_downside_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    closes = [100.0, 101.0, 102.0, 103.0]
    payload = make_history_payload(closes, ticker="POS")
    monkeypatch.setattr(metrics, "get_history", lambda *_, **__: payload)

    result = metrics.advanced_metrics("pos", date(2024, 1, 1), date(2024, 1, 4), rf=0.0, mar=0.5)
    expected = _expected_advanced_metrics(closes, rf=0.0, mar=0.5)

    assert result["downside_volatility"] is None
    assert result["sortino"] is None
    assert result["calmar"] is None


def test_advanced_metrics_ytd_none_when_single_current_year(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "ticker": "MIX",
        "start": "2023-12-31",
        "end": None,
        "count": 2,
        "data": [
            {"date": "2023-12-31", "close": 100.0},
            {"date": "2024-01-02", "close": 101.0},
        ],
    }
    monkeypatch.setattr(metrics, "get_history", lambda *_, **__: payload)

    result = metrics.advanced_metrics("mix", date(2023, 12, 31), rf=0.0, mar=0.0)

    assert result["n"] == 2
    assert result["ytd_return"] is None
