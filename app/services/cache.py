import asyncio
import json
from datetime import datetime, timedelta

from redis.asyncio import Redis

import app.constants as const
from app.crud import get_user_by_telegram_id
from app.database.postgres import session_maker
from app.database.redis import redis_client
from app.journal_api import JournalClient
from app.logger import logger

api_semaphore = asyncio.Semaphore(3)


async def get_cached_schedule_date(client: JournalClient, group_id: int, date: str):
    cache_key = f"cache:schedule:{group_id}:{date}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    url = const.GET_SCHEDULE_BY_DATE_URL.format(date=date)
    schedule_data = await client.make_request(url)

    if schedule_data:
        await redis_client.set(cache_key, json.dumps(schedule_data), ex=43200)
    return schedule_data or []


async def get_cached_schedule_range(client: JournalClient, group_id: int):
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    start_str = start_of_week.strftime("%Y-%m-%d")
    end_str = end_of_week.strftime("%Y-%m-%d")

    cache_key = f"cache:schedule:week:{group_id}:{start_str}"

    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    url = const.GET_SCHEDULE_RANGE_URL.format(start=start_str, end=end_str)
    schedule_data = await client.make_request(url)

    if schedule_data:
        await redis_client.set(cache_key, json.dumps(schedule_data), ex=43200)

    return schedule_data or []


async def update_leaders(client: JournalClient):
    leaders = await client.make_request(const.GET_STREAM_LEADERS_URL)
    await redis_client.set("cache:leaderboard", json.dumps(leaders), ex=3600)


async def get_homeworks_with_status(
    client: JournalClient, status: int, group_id: int
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
            response_data = await client.make_request(url)

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
        average_attendance = 0
        counts = {0: 0, 3: 0, 5: 0}

        try:
            counters_raw = await client.make_request(const.GET_HOMEWORKS_COUNT_URL)
            remote_counts = {
                item["counter_type"]: item["counter"] for item in counters_raw
            }
            for status in [0, 3, 5]:
                counts[status] = remote_counts.get(status, 0)
        except Exception as e:
            logger.error(f"Failed to fetch homework counts for {telegram_id}: {e}")

        try:
            score_per_month = await client.make_request(const.GET_AVERAGE_SCORE_URL)
            attendance_per_month = await client.make_request(const.GET_ATTENDANCE_URL)
            current_month = datetime.now().strftime("%Y-%m-01")
            for date in score_per_month:
                if date.get("date") == current_month:
                    average_score = date.get("points")
                    break
            for date in attendance_per_month:
                if date.get("date") == current_month:
                    average_attendance = date.get("points")
                    break
        except Exception as e:
            logger.error(f"Failed to fetch user info for {telegram_id}: {e}")
        print(average_attendance)
        user_info = {
            "average_score": average_score,
            "average_attendance": average_attendance,
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


async def clear_user_redis_data(redis: Redis, telegram_id: int):
    pattern = f"user:{telegram_id}:*"
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)
    await redis.delete(f"lock:update:{telegram_id}")
