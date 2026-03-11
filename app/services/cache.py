from datetime import datetime
import json

from app.database.redis import redis_client
from app.config import config
from app.journal_api import JournalClient
from app.logger import logger

import app.constants as const


async def update_schedule(client: JournalClient):
    today_schedule = await client._make_request(const.GET_SCHEDULE_BY_DATE_URL+datetime.now().strftime("%Y-%m-%d"))
    await redis_client.set("cache:schedule:today", json.dumps(today_schedule))


async def update_leaders(client: JournalClient):
    leaders = await client._make_request(const.GET_STREAM_LEADERS_URL)
    await redis_client.set("cache:leaderboard", json.dumps(leaders), ex=3600)


async def update_user_info(client: JournalClient, telegram_id: int):
    score_per_month: list[dict] = await client._make_request(const.GET_AVERAGE_SCORE_URL)
    for date in score_per_month:
        if date.get("date") == datetime.now().strftime("%Y-%m-01"):
            average_score = date.get("points")
            break
    
    user_info = {
        "average_score": average_score,
    }
    await redis_client.set(f"user:{telegram_id}:info", json.dumps(user_info), ex=86400)


async def update_cache():
    client = JournalClient(
        username=config.SERVICE_USER_LOGIN,
        password=config.SERVICE_USER_PASSWORD,
        telegram_id="SERVICE",
        redis_client=redis_client,
    )
    await client.login()
    try:
        await update_schedule(client)
        await update_leaders(client)
    except Exception as e:
        logger.error(e)
        raise e


