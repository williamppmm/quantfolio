from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    volume: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        Index("ix_prices_ticker_date", "ticker", "date", unique=True),
    )


class TransactionType(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    FEE = "FEE"


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="portfolio",
        cascade="all, delete-orphan",
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type"),
        nullable=False,
    )
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    portfolio: Mapped[Portfolio] = relationship(back_populates="transactions")

    __table_args__ = (
        Index("ix_transactions_portfolio_ticker_date", "portfolio_id", "ticker", "date"),
        CheckConstraint(
            "(type IN ('BUY','SELL') AND quantity IS NOT NULL AND quantity > 0 AND price IS NOT NULL AND price >= 0)"
            " OR (type NOT IN ('BUY','SELL'))",
            name="ck_transactions_buy_sell_requirements",
        ),
        CheckConstraint(
            "(type IN ('DIVIDEND','FEE') AND amount IS NOT NULL AND amount >= 0)"
            " OR (type NOT IN ('DIVIDEND','FEE'))",
            name="ck_transactions_credit_requirements",
        ),
        CheckConstraint(
            "date <= CURRENT_DATE",
            name="ck_transactions_not_future",
        ),
        CheckConstraint(
            "ticker = upper(ticker)",
            name="ck_transactions_ticker_upper",
        ),
    )
