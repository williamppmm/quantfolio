from datetime import date

import pandas as pd
import pytest
from fastapi import HTTPException

from backend.app.services import market_data
from tests.helpers import make_market_dataframe


def test_get_last_close_success(monkeypatch: pytest.MonkeyPatch) -> None:
    df = make_market_dataframe([100.0, 101.25, 102.5], tz="UTC")
    monkeypatch.setattr("backend.app.services.market_data.yf.download", lambda **_: df)

    result = market_data.get_last_close("voo")

    assert result["ticker"] == "VOO"
    assert result["date"] == "2024-01-03"
    assert result["close"] == pytest.approx(102.5)


def test_get_last_close_download_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(**_: object) -> pd.DataFrame:  # pragma: no cover - signature only
        raise RuntimeError("boom")

    monkeypatch.setattr("backend.app.services.market_data.yf.download", _raise)

    with pytest.raises(HTTPException) as exc:
        market_data.get_last_close("spy")

    assert exc.value.status_code == 502
    assert "Error downloading data" in exc.value.detail


def test_get_last_close_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.market_data.yf.download",
        lambda **_: pd.DataFrame(),
    )

    with pytest.raises(HTTPException) as exc:
        market_data.get_last_close("iwm")

    assert exc.value.status_code == 404


def test_get_last_close_dropna_removes_all(monkeypatch: pytest.MonkeyPatch) -> None:
    df = make_market_dataframe([None, None], tz="UTC")
    monkeypatch.setattr("backend.app.services.market_data.yf.download", lambda **_: df)

    with pytest.raises(HTTPException) as exc:
        market_data.get_last_close("ndx")

    assert exc.value.status_code == 404


def test_get_history_success_with_ohlc(monkeypatch: pytest.MonkeyPatch) -> None:
    df = make_market_dataframe([100.0, 101.5, 99.5], tz="UTC", volumes=[1000, 2000, 3000])
    monkeypatch.setattr("backend.app.services.market_data.yf.download", lambda **_: df)

    result = market_data.get_history("aapl", date(2024, 1, 1), date(2024, 1, 3), interval="1d")

    assert result["ticker"] == "AAPL"
    assert result["interval"] == "1d"
    assert result["start"] == "2024-01-01"
    assert result["end"] == "2024-01-03"
    assert result["count"] == 3

    first, last = result["data"][0], result["data"][-1]
    assert first == {
        "date": "2024-01-01",
        "open": pytest.approx(100.0),
        "high": pytest.approx(100.0),
        "low": pytest.approx(100.0),
        "close": pytest.approx(100.0),
        "volume": 1000,
    }
    assert last["date"] == "2024-01-03"
    assert last["close"] == pytest.approx(99.5)


def test_get_history_handles_close_only(monkeypatch: pytest.MonkeyPatch) -> None:
    idx = pd.date_range("2024-01-01", periods=2, tz="UTC")
    df = pd.DataFrame({"Close": [50.0, 51.0]}, index=idx)
    monkeypatch.setattr("backend.app.services.market_data.yf.download", lambda **_: df)

    result = market_data.get_history("tsla", date(2024, 1, 1), date(2024, 1, 2))
    candle = result["data"][0]
    assert candle["date"] == "2024-01-01"
    assert candle["close"] == pytest.approx(50.0)
    assert candle.get("volume") is None


def test_get_history_volume_defaults_to_zero_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    df = make_market_dataframe([110.0, 111.0], tz="UTC")
    df = df.drop(columns=["Volume"])
    monkeypatch.setattr("backend.app.services.market_data.yf.download", lambda **_: df)

    result = market_data.get_history("msft", date(2024, 1, 1), date(2024, 1, 2))

    assert result["data"][1]["volume"] is None


def test_get_history_validates_dates() -> None:
    with pytest.raises(HTTPException) as exc:
        market_data.get_history("qqq", date(2024, 1, 5), date(2024, 1, 4))

    assert exc.value.status_code == 422
    assert "start must be on or before end" in exc.value.detail


def test_get_history_download_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.market_data.yf.download",
        lambda **_: (_ for _ in ()).throw(RuntimeError("network")),
    )

    with pytest.raises(HTTPException) as exc:
        market_data.get_history("dia", date(2024, 1, 1), date(2024, 1, 2))

    assert exc.value.status_code == 502


def test_get_history_empty_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.app.services.market_data.yf.download", lambda **_: pd.DataFrame())

    with pytest.raises(HTTPException) as exc:
        market_data.get_history("uso", date(2024, 1, 1), date(2024, 1, 2))

    assert exc.value.status_code == 404


def test_get_history_dropna_results_in_empty_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    df = make_market_dataframe([None, None, None], tz="UTC", volumes=[None, None, None])
    monkeypatch.setattr("backend.app.services.market_data.yf.download", lambda **_: df)

    with pytest.raises(HTTPException) as exc:
        market_data.get_history("ibo", date(2024, 1, 1), date(2024, 1, 3))

    assert exc.value.status_code == 404
