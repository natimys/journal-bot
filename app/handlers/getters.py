import json

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from redis.asyncio import Redis

from app.logger import logger
from app.text import text_manager

router = Router()


@router.message(Command("get_schedule"))
async def cmd_get_schedule(message: Message, redis: Redis):
    schedule = await redis.get("cache:schedule:today")
    if schedule:
        schedule = json.loads(schedule)
    lines = [
        text_manager.get("schedule_entry").format(started_at=item["started_at"], finished_at=item["finished_at"], subject_name=item["subject_name"])
        for i, item in enumerate(schedule, 1)
    ]
    text = text_manager.get("schedule_title") + "\n\n" + "\n".join(lines) if lines else text_manager.get("schedule_empty")
    logger.info(f"get_schedule called, responsed to @{message.from_user.username}")
    await message.answer(text)


@router.message(Command("get_leaderboard"))
async def cmd_get_leaderboard(message: Message, redis: Redis):
    leaderboard = await redis.get("cache:leaderboard")
    if leaderboard:
        leaderboard = json.loads(leaderboard)
    lines = [
        text_manager.get("leaderboard_entry").format(i=i, name=item["full_name"], score=item["amount"])
        for i, item in enumerate(leaderboard, 1)
    ]
    text = text_manager.get("leaderboard_title") + "\n\n" + "\n".join(lines)
    logger.info(f"get_leaderboard called, responsed to @{message.from_user.username}")
    await message.answer(text)
