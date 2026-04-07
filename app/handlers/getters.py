import json

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton
from redis.asyncio import Redis

from app.logger import logger
from app.text import text_manager

router = Router()


async def format_schedule(schedule: dict):
    lines = [
        text_manager.get("schedule_entry").format(
            started_at=item["started_at"],
            finished_at=item["finished_at"],
            subject_name=item["subject_name"],
        )
        for item in schedule
    ]
    text = (
        text_manager.get("schedule_title") + "\n\n" + "\n".join(lines)
        if lines
        else text_manager.get("schedule_empty")
    )
    return text


@router.callback_query(F.data.startswith("get_schedule:"))
async def get_schedule(callback: CallbackQuery, redis: Redis):
    logger.info(f"received get_schedule call from {callback.from_user.id}")
    day_type = callback.data.split(":")[1]
    redis_key = f"cache:schedule:{day_type}"
    schedule_raw = await redis.get(redis_key)
    await callback.answer()

    if not schedule_raw:
        return await callback.answer(text_manager.get("schedule_empty"))

    schedule = json.loads(schedule_raw)
    text = await format_schedule(schedule)
    back_to_menu_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:homeworks_menu")]
        ]
    )
    logger.info(
        f"schedule {day_type} called, responsed to @{callback.from_user.username}"
    )
    await callback.message.edit_text(text, reply_markup=back_to_menu_button)


@router.callback_query(F.data == "get_leaderboard")
async def get_leaderboard(callback: CallbackQuery, redis: Redis):
    await callback.answer()
    leaderboard = await redis.get("cache:leaderboard")
    if leaderboard:
        leaderboard = json.loads(leaderboard)
    lines = [
        text_manager.get("leaderboard_entry").format(
            i=i, name=item["full_name"], score=item["amount"]
        )
        for i, item in enumerate(leaderboard, 1)
    ]
    back_to_menu_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")]
        ]
    )
    text = text_manager.get("leaderboard_title") + "\n\n" + "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=back_to_menu_button)
