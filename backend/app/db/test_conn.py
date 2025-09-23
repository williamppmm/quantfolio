import asyncio
from sqlalchemy import text

from .session import get_engine


async def main():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        print("DB OK:", result.scalar_one())


if __name__ == "__main__":
    asyncio.run(main())
