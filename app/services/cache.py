import asyncio
import json
from datetime import datetime
from typing import Literal

from redis.asyncio import Redis

import app.constants as const
from app.config import config
from app.crud import get_user_by_telegram_id
from app.database.postgres import session_maker
from app.database.redis import redis_client
from app.journal_api import JournalClient
from app.logger import logger

api_semaphore = asyncio.Semaphore(3)


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
    """получение домашек с опр. статусом

    Args:
        client (JournalClient): Клиент журнала
        status (Literal[0, 1, 2, 3, 5]): 0 - просрочка 3 - активные 5 - удаленные, остальное в constants
        group_id (int): ID группы пользователя

    """
    homeworks = []
    page = 1
    seen_ids = set()

    while page <= 50:
        url = const.GET_HOMEWORKS_URL.format(
            page=page, status=status, group_id=group_id
        )
        try:
            response_data = await client._make_request(url)

            if not response_data:
                break

            added_on_this_page = 0
            for hw in response_data:
                hw_id = hw.get("id")
                if hw_id in seen_ids:
                    continue

                seen_ids.add(hw_id)
                added_on_this_page += 1

                await redis_client.set(
                    f"hw:content:{hw_id}",
                    json.dumps(
                        {
                            "subject": hw.get("name_spec"),
                            "description": hw.get("theme"),
                            "file_url": hw.get("file_path"),
                            "teacher": hw.get("fio_teach"),
                            "comment": hw.get("comment"),
                            "overdue_time": hw.get("overdue_time"),
                        }
                    ),
                    ex=604800,
                )

                homeworks.append(
                    {
                        "id": hw_id,
                        "subject": hw.get("name_spec"),
                        "date_limit": hw.get("overdue_time"),
                    }
                )

            if added_on_this_page == 0:
                break

            page += 1
            await asyncio.sleep(0.2)

        except Exception as e:
            logger.error(f"Error at page {page}: {e}")
            break
    return homeworks


async def update_all_homeworks_cache(
    client: JournalClient, telegram_id: int, group_id: int
):
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
        f"user:{telegram_id}:homeworks_full", json.dumps(all_data), ex=10800
    )
    return counts


async def update_user_info(client: JournalClient, telegram_id: int):
    """Обновляет и отдает в redis информацию о пользователе

    Args:
        client (JournalClient): Клиент журнала
        telegram_id (int): Telegram ID пользователя
    """

    try:
        average_score = 0
        counts = {0: 0, 3: 0, 5: 0}

        try:
            counters_raw = await client._make_request(const.GET_HOMEWORKS_COUNT_URL)
            remote_counts = {
                item["counter_type"]: item["counter"] for item in counters_raw
            }
            for status in [0, 3, 5]:
                counts[status] = remote_counts.get(status, 0)
        except Exception as e:
            logger.error(f"Failed to fetch homework counts for {telegram_id}: {e}")

        try:
            score_per_month = await client._make_request(const.GET_AVERAGE_SCORE_URL)
            current_month = datetime.now().strftime("%Y-%m-01")
            for date in score_per_month:
                if date.get("date") == current_month:
                    average_score = date.get("points")
                    break
        except Exception:
            pass

        user_info = {
            "average_score": average_score,
            "expired_count": counts.get(0, 0),
            "active_count": counts.get(3, 0),
            "deleted_count": counts.get(5, 0),
        }
        await redis_client.set(
            f"user:{telegram_id}:info", json.dumps(user_info), ex=10800
        )

        async with session_maker() as session:
            user = await get_user_by_telegram_id(session, telegram_id)
            gid = int(user.group) if user and user.group else None

        if gid:
            await update_all_homeworks_cache(client, telegram_id, gid)

    except Exception as e:
        logger.error(f"Global error in update_user_info for {telegram_id}: {e}")


# ПЕРЕДЕЛАТЬ, РАСПИСАНИЕ БЕРЕТСЯ ТОЛЬКО ИЗ ГРУППЫ СЕРВИСНОГО ЮЗЕРА
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
        await client.close()


async def clear_user_redis_data(redis: Redis, telegram_id: int):
    pattern = f"user:{telegram_id}:*"
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)
    await redis.delete(f"lock:update:{telegram_id}")
