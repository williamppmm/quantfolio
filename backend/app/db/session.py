from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ..core.settings import get_settings

_engine: AsyncEngine | None = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None


def configure_engine(database_url: str | None = None) -> None:
    global _engine, SessionLocal
    settings = get_settings()
    url = database_url or settings.database_url
    _engine = create_async_engine(url, echo=settings.env.lower() == "dev", future=True)
    SessionLocal = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


def _require_session_local() -> async_sessionmaker[AsyncSession]:
    if SessionLocal is None:
        configure_engine()
    return SessionLocal  # type: ignore[return-value]


def _require_engine() -> AsyncEngine:
    if _engine is None:
        configure_engine()
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return _require_session_local()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    maker = _require_session_local()
    async with maker() as session:
        yield session


def get_engine() -> AsyncEngine:
    return _require_engine()


async def check_connection() -> None:
    engine = _require_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


configure_engine()
