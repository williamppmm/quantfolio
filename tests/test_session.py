from __future__ import annotations

import pytest
from sqlalchemy import text

from backend.app.db import session as db_session


@pytest.mark.asyncio
async def test_session_configuration(tmp_path):
    db_file = tmp_path / "session.db"
    db_session.configure_engine(f"sqlite+aiosqlite:///{db_file}")
    maker = db_session.get_sessionmaker()
    assert maker is not None

    async with maker() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
