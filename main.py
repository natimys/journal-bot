import asyncio
from app.bot import run_bot
from app.database.postgres import engine
from app.database.redis import close_redis
from app.models import Base


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    await init_db()
    try:
        await run_bot()
    finally:
        await engine.dispose()
        await close_redis()


if __name__ == "__main__":
    try:
        print("Starting bot...")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")
