import asyncio
from app.bot import run_bot
from app.models import Base
from app.engine import engine

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def main():
    await init_db()
    await run_bot()

if __name__ == "__main__":
    asyncio.run(main())