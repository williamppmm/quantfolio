from __future__ import annotations

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure project root on sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.db.base import Base
from backend.app.db.session import configure_engine, get_engine, get_sessionmaker
from backend.app.main import app


@pytest_asyncio.fixture(scope="session")
async def setup_test_db(tmp_path_factory: pytest.TempPathFactory):
    db_dir = tmp_path_factory.mktemp("db")
    db_path = db_dir / "test.db"
    configure_engine(f"sqlite+aiosqlite:///{db_path}")
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_database(setup_test_db):
    engine = get_engine()
    async with engine.begin() as conn:
        # Ensure tables exist in case another test reconfigured the engine
        await conn.run_sync(Base.metadata.create_all)
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def db_session(setup_test_db):
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(setup_test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
