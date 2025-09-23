from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Sequence
from uuid import UUID

import numpy as np
import pandas as pd
from fastapi import HTTPException

from ..db.crud_prices import get_latest_prices_for, load_price_history_for_tickers
from ..db.crud_transactions import aggregate_positions, get_all_transactions
from ..db.models import Transaction, TransactionType
from ..schemas import PositionOut, PortfolioMetricsResponse
from .market_data import get_history, get_last_close

_PRICE_QUANT = Decimal("0.0001")
_VALUE_QUANT = Decimal("0.01")
_QTY_QUANT = Decimal("0.00000001")


def _quantize(value: Decimal | None, quantum: Decimal) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _decimal_from(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


async def compute_positions(
    session,
    *,
    portfolio_id: UUID,
) -> List[PositionOut]:
    aggregates = await aggregate_positions(session, portfolio_id=portfolio_id)
    if not aggregates:
        return []

    filtered = [row for row in aggregates if _decimal_from(row.get("quantity")) != 0]
    if not filtered:
        return []

    tickers = [row["ticker"] for row in filtered]
    db_prices = await get_latest_prices_for(session, tickers)
    missing = [ticker for ticker in tickers if ticker not in db_prices or db_prices[ticker].close is None]

    fallback_prices: Dict[str, Decimal] = {}
    if missing:
        for ticker in missing:
            try:
                payload = await asyncio.to_thread(get_last_close, ticker)
            except HTTPException:
                continue
            fallback_prices[ticker] = Decimal(str(payload["close"]))

    results: List[PositionOut] = []
    for row in filtered:
        ticker = row["ticker"]
        quantity = _decimal_from(row.get("quantity")).quantize(_QTY_QUANT, rounding=ROUND_HALF_UP)
        cost = _decimal_from(row.get("cost"))
        avg_cost = cost / quantity if quantity != 0 else None

        price_record = db_prices.get(ticker)
        market_price = None
        if price_record and price_record.close is not None:
            market_price = _decimal_from(price_record.close)
        elif ticker in fallback_prices:
            market_price = fallback_prices[ticker]

        market_value = (market_price * quantity) if market_price is not None else Decimal(0)
        unrealized = Decimal(0)
        if market_price is not None and avg_cost is not None:
            unrealized = (market_price - avg_cost) * quantity

        results.append(
            PositionOut(
                ticker=ticker,
                quantity=_quantize(quantity, _QTY_QUANT),
                avg_cost=_quantize(avg_cost, _PRICE_QUANT) if avg_cost is not None else None,
                market_price=_quantize(market_price, _PRICE_QUANT) if market_price is not None else None,
                market_value=_quantize(market_value, _VALUE_QUANT),
                unrealized_pnl=_quantize(unrealized, _VALUE_QUANT),
            )
        )

    results.sort(key=lambda position: position.ticker)
    return results


async def _ensure_price_history(
    tickers: Sequence[str],
    start: date,
    end: date,
    db_prices: Dict[str, list],
) -> pd.DataFrame:
    rows: List[dict] = []
    missing: List[str] = []
    for ticker in tickers:
        items = db_prices.get(ticker, [])
        if not items:
            missing.append(ticker)
            continue
        for price in items:
            if price.close is None:
                continue
            rows.append({"date": pd.Timestamp(price.date), "ticker": ticker, "close": float(price.close)})

    for ticker in missing:
        try:
            payload = await asyncio.to_thread(get_history, ticker, start, end, "1d")
        except HTTPException as exc:
            raise HTTPException(status_code=400, detail=f"Missing price data for {ticker}: {exc.detail}") from exc
        for item in payload.get("data", []):
            rows.append({"date": pd.Timestamp(item["date"]), "ticker": ticker, "close": float(item["close"])})

    price_df = pd.DataFrame(rows)
    if price_df.empty:
        raise HTTPException(status_code=400, detail="No price data available for requested portfolio.")
    return price_df


def _timeseries_positions(transactions: List[Transaction], tickers: Sequence[str], date_index: pd.DatetimeIndex) -> pd.DataFrame:
    records: List[dict] = []
    for tx in transactions:
        if tx.type in {TransactionType.BUY, TransactionType.SELL}:
            qty = float(tx.quantity or 0)
            if tx.type == TransactionType.SELL:
                qty *= -1
            if qty != 0:
                records.append({"date": pd.Timestamp(tx.date), "ticker": tx.ticker, "qty_delta": qty})

    if records:
        qty_df = pd.DataFrame(records)
        qty_pivot = qty_df.pivot_table(index="date", columns="ticker", values="qty_delta", aggfunc="sum", fill_value=0.0)
    else:
        qty_pivot = pd.DataFrame(0.0, index=pd.DatetimeIndex([], name="date"), columns=tickers)

    qty_pivot = qty_pivot.reindex(date_index, fill_value=0.0)
    qty_pivot = qty_pivot.reindex(columns=tickers, fill_value=0.0)
    return qty_pivot.cumsum()


def _compute_returns(values: pd.Series, start: date) -> np.ndarray:
    returns: List[float] = []
    for idx in range(1, len(values)):
        prev_date = values.index[idx - 1]
        current_date = values.index[idx]
        if prev_date.date() < start:
            continue
        prev_value = values.iloc[idx - 1]
        current_value = values.iloc[idx]
        if prev_value <= 0:
            continue
        returns.append((current_value / prev_value) - 1.0)
    return np.array(returns, dtype=float)


async def compute_portfolio_metrics(
    session,
    *,
    portfolio_id: UUID,
    start: date,
    end: date,
    rf: float,
    mar: float,
) -> PortfolioMetricsResponse:
    if start > end:
        raise HTTPException(status_code=400, detail="start must be before or equal to end")

    transactions = await get_all_transactions(session, portfolio_id=portfolio_id, up_to=end)
    if not transactions:
        raise HTTPException(status_code=400, detail="Portfolio has no transactions in the requested range")

    tickers = sorted({tx.ticker for tx in transactions})
    if not tickers:
        raise HTTPException(status_code=400, detail="Portfolio has no equity transactions")

    first_tx_date = min(tx.date for tx in transactions)
    effective_start = min(first_tx_date, start)
    date_index = pd.date_range(effective_start, end, freq="D")

    positions = _timeseries_positions(transactions, tickers, date_index)

    price_records = await load_price_history_for_tickers(session, tickers, effective_start, end)
    price_df = await _ensure_price_history(tickers, effective_start, end, price_records)
    prices = price_df.pivot_table(index="date", columns="ticker", values="close", aggfunc="last")
    prices = prices.sort_index().reindex(date_index)
    prices = prices.ffill().reindex(columns=tickers)

    valid_columns = [col for col in prices.columns if prices[col].notna().any()]
    if not valid_columns:
        raise HTTPException(status_code=400, detail="Price data is unavailable for the requested tickers")

    prices = prices[valid_columns]
    positions = positions[valid_columns]
    active_tickers = [ticker for ticker in valid_columns if positions[ticker].abs().max() > 0]
    if not active_tickers:
        raise HTTPException(status_code=400, detail="No active positions to analyze in the selected period")

    positions = positions[active_tickers]
    prices = prices[active_tickers]

    values = (positions * prices).sum(axis=1).fillna(0.0)
    if values.loc[start:].le(0).all():
        raise HTTPException(status_code=400, detail="Portfolio value is zero throughout the selected period")

    returns = _compute_returns(values, start)
    n_days = returns.size
    if n_days == 0:
        raise HTTPException(status_code=400, detail="Not enough observations to compute metrics")

    rf_daily = (1 + rf) ** (1 / 252) - 1
    mar_daily = (1 + mar) ** (1 / 252) - 1

    total_growth = float(np.prod(returns + 1.0))
    ann_return = total_growth ** (252 / n_days) - 1 if total_growth > 0 else None

    std_daily = float(np.std(returns, ddof=0))
    ann_volatility = std_daily * np.sqrt(252) if std_daily > 0 else None

    sharpe = None
    if std_daily > 0:
        mean_daily = float(np.mean(returns))
        sharpe = ((mean_daily - rf_daily) / std_daily) * np.sqrt(252)

    downside_mask = returns < mar_daily
    if downside_mask.any():
        downside_diff = returns[downside_mask] - mar_daily
        downside_std = float(np.sqrt(np.mean(downside_diff ** 2)))
    else:
        downside_std = 0.0
    downside_volatility = downside_std * np.sqrt(252) if downside_std > 0 else None

    sortino = None
    if downside_volatility and downside_volatility > 0 and ann_return is not None:
        sortino = (ann_return - mar) / downside_volatility

    values_array = values.values.astype(float)
    cummax = np.maximum.accumulate(values_array)
    drawdowns = np.where(cummax > 0, (values_array / cummax) - 1.0, 0.0)
    max_drawdown = float(drawdowns.min()) if drawdowns.size else 0.0

    calmar = None
    if max_drawdown < 0 and ann_return is not None:
        calmar = ann_return / abs(max_drawdown)

    return PortfolioMetricsResponse(
        portfolio_id=portfolio_id,
        start=start,
        end=end,
        n_days=int(n_days),
        tickers=active_tickers,
        ann_return=float(ann_return) if ann_return is not None else None,
        ann_volatility=float(ann_volatility) if ann_volatility is not None else None,
        sharpe=float(sharpe) if sharpe is not None else None,
        sortino=float(sortino) if sortino is not None else None,
        calmar=float(calmar) if calmar is not None else None,
        max_drawdown=max_drawdown,
        downside_volatility=float(downside_volatility) if downside_volatility is not None else None,
        rf=rf,
        mar=mar,
    )
