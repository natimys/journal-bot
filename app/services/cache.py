from datetime import datetime
import json
from typing import Literal
import asyncio

from curl_cffi.requests.exceptions import HTTPError

from app.database.postgres import session_maker
from app.database.redis import redis_client
from app.config import config
from app.crud import get_user_by_telegram_id
from app.journal_api import JournalClient
from app.logger import logger

import app.constants as const


async def update_schedule(client: JournalClient):
    today_schedule = await client._make_request(
        const.GET_SCHEDULE_BY_DATE_URL + datetime.now().strftime("%Y-%m-%d")
    )
    await redis_client.set("cache:schedule:today", json.dumps(today_schedule))


async def update_leaders(client: JournalClient):
    leaders = await client._make_request(const.GET_STREAM_LEADERS_URL)
    await redis_client.set("cache:leaderboard", json.dumps(leaders), ex=3600)


async def get_homeworks_with_status(
    client: JournalClient, status: Literal[0, 1, 2, 3, 5], group_id: int
) -> list[dict]:
    """_summary_

    Args:
        client (JournalClient): Клиент журнала
        status (Literal[0, 1, 2, 3, 5]): 0 - просрочка 3 - активные 5 - удаленные, остальное в constants
        group_id (int): ID группы пользователя

    """
    homeworks = []
    page = 1

    max_pages = 50
    while True:
        try:
            url = const.GET_HOMEWORKS_URL.format(
                page=page, status=status, group_id=group_id
            )
            response_data = await client._make_request(url)

            if not isinstance(response_data, list):
                logger.error(
                    f"Unexpected homework response type {type(response_data)} for"
                    f" status={status}, page={page}, gid={group_id}"
                )
                break

            if not response_data:
                break

            homeworks.extend(response_data)
            page += 1

            if page > max_pages:
                logger.warning(
                    f"Reached page limit ({max_pages}) for homeworks (status={status}, gid={group_id}),"
                    " stopping to avoid infinite loop."
                )
                break
        except HTTPError as e:
            if e.code == 404:
                logger.info(f"Getting homeworks ended at {page-1}. Status: {status}")
                break
            if e.code == 401:
                logger.warning(f"Unauthorized when fetching homeworks (status={status}, page={page}, gid={group_id}). Stopping.")
                break
            raise e
        await asyncio.sleep(0.3)
    return homeworks


async def get_count_homeworks_with_status(
    client: JournalClient, status: Literal[0, 1, 2, 3, 5], group_id: int
):
    homeworks = await get_homeworks_with_status(client, status, group_id)
    return len(homeworks)

async def update_all_homeworks_cache(client: JournalClient, telegram_id: int, group_id: int):
    """
    Собирает ДЗ всех статусов и сохраняет в редис, возвращает счетчики для статистики.
    """
    all_data = {}
    counts = {}
    
    for status in [0, 3, 5]:
        hw_list = await get_homeworks_with_status(client, status, group_id)
        all_data[status] = hw_list
        counts[status] = len(hw_list)

    await redis_client.set(
        f"user:{telegram_id}:homeworks_full", 
        json.dumps(all_data), 
        ex=10800
    )
    return counts


async def update_user_info(client: JournalClient, telegram_id: int):
    """Обновляет и отдает в redis информацию о пользователе

    Args:
        client (JournalClient): Клиент журнала
        telegram_id (int): Telegram ID пользователя
    """
    average_score = 0
    try:
        score_per_month: list[dict] = await client._make_request(
            const.GET_AVERAGE_SCORE_URL
        )
        for date in score_per_month:
            if date.get("date") == datetime.now().strftime("%Y-%m-01"):
                average_score = date.get("points")
                break
    except Exception as e:
        logger.error(f"Failed to fetch average score for {telegram_id}: {e}")

    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, telegram_id)

    try:
        gid = int(user.group) if user.group is not None else None
    except ValueError:
        gid = None

    counts = {0: 0, 3: 0, 5: 0}
    if gid is not None:
        try:
            counts = await update_all_homeworks_cache(client, telegram_id, gid)
        except HTTPError as e:
            logger.error(f"Failed to update homeworks cache for {telegram_id}, gid={gid}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error while updating homeworks for {telegram_id}: {e}")

    user_info = {
        "average_score": average_score,
        "expired_count": counts.get(0, 0),
        "active_count": counts.get(3, 0),
        "deleted_count": counts.get(5, 0),
    }
    await redis_client.set(f"user:{telegram_id}:info", json.dumps(user_info), ex=10800)


async def update_cache():
    """Обновление общего кеша

    Берет данные сервисного клиента из окружения, получает данные и кеширует в redis
    """
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
    finally:
        client.close()
