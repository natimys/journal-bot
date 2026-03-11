import asyncio
from app.bot import run_bot
from app.database.postgres import engine
from app.database.redis import close_redis
from app.models import Base
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.cache import update_schedule
from app.services.cache import update_cache

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    await init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(update_cache, "cron", minute=0)
    scheduler.start()
    
    await update_cache()

    try:
        await run_bot()
    finally:
        scheduler.shutdown()
        await engine.dispose()
        await close_redis()


if __name__ == "__main__":
    try:
        print("Starting bot...")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")
