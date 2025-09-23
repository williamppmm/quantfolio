"""add portfolios and transactions

Revision ID: 371f8414c52d
Revises: 9b225c7d705e
Create Date: 2025-09-22 19:22:07.028679

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "371f8414c52d"
down_revision: Union[str, Sequence[str], None] = "9b225c7d705e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TRANSACTION_TYPE_ENUM_NAME = "transaction_type"

def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("BUY", "SELL", "DIVIDEND", "FEE", name=TRANSACTION_TYPE_ENUM_NAME),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("price", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("amount", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(type IN ('BUY','SELL') AND quantity IS NOT NULL AND quantity > 0 AND price IS NOT NULL AND price >= 0)"
            " OR (type NOT IN ('BUY','SELL'))",
            name="ck_transactions_buy_sell_requirements",
        ),
        sa.CheckConstraint(
            "(type IN ('DIVIDEND','FEE') AND amount IS NOT NULL AND amount >= 0)"
            " OR (type NOT IN ('DIVIDEND','FEE'))",
            name="ck_transactions_credit_requirements",
        ),
        sa.CheckConstraint("date <= CURRENT_DATE", name="ck_transactions_not_future"),
        sa.CheckConstraint("ticker = upper(ticker)", name="ck_transactions_ticker_upper"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transactions_portfolio_ticker_date",
        "transactions",
        ["portfolio_id", "ticker", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_portfolio_ticker_date", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("portfolios")
    op.execute(sa.text(f"DROP TYPE IF EXISTS {TRANSACTION_TYPE_ENUM_NAME}"))
