import json

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import get_user_by_telegram_id
from app.journal_api import JournalClient
from app.logger import logger
from app.security import decrypt_password
from app.services.cache import update_leaders
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


@router.callback_query(F.data == "get_leaderboard")
async def get_leaderboard(callback: CallbackQuery, redis: Redis, session: AsyncSession):
    await callback.answer()
    leaderboard = await redis.get("cache:leaderboard")
    if leaderboard:
        leaderboard = json.loads(leaderboard)
    else:
        user_id = callback.from_user.id
        user = await get_user_by_telegram_id(session, user_id)
        client = JournalClient(
            username=user.journal_login,
            password=decrypt_password(user.journal_password),
            telegram_id=callback.from_user.id,
            redis_client=redis
        )
        await update_leaders(client)
        leaderboard = await redis.get("cache:leaderboard")
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
