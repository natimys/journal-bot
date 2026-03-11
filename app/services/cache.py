import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database.redis import redis_client
from app.config import config
from app.journal_api import JournalClient
from app.logger import logger

import app.constants as const


async def update_schedule(client: JournalClient):
    today_schedule = await client._make_request(const.GET_SCHEDULE_BY_DATE_URL+datetime.now().strftime("%d-%m-%Y"))
    await redis_client.set("cache:schedule:today", today_schedule)


async def update_leaders(client: JournalClient):
    leaders = await client._make_request(const.GET_STREAM_LEADERS_URL)
    await redis_client.set("cache:leaders", leaders)


async def update_cache():
    client = JournalClient(
        username=config.SERVICE_USER_LOGIN,
        password=config.SERVICE_USER_PASSWORD,
        telegram_id="SERVICE",
        redis_client=redis_client,
    )
    await client.login()
    try:
        await update_schedule()
        await update_leaders()
    except Exception as e:
        logger.error(e)
        raise e


scheduler = AsyncIOScheduler()
scheduler.add_job(update_schedule, "interval", hours=1)