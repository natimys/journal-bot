import json
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

from app.text import text_manager
from app.crud import get_user_by_telegram_id, create_user
from app.database.redis import Redis
from app.handlers.getters import get_schedule, get_leaderboard
from app.services.cache import update_user_info
from app.journal_api import JournalClient
from app.security import decrypt_password
from app.logger import logger
from app.services.user import get_user_homeworks_stats

router = Router()


async def check_user_exists(event: Message | CallbackQuery, session: AsyncSession):
    if isinstance(event, CallbackQuery):
        user_id = event.from_user.id
        username = event.from_user.first_name
    else:
        user_id = event.from_user.id
        username = event.from_user.first_name

    user = await get_user_by_telegram_id(session, user_id)
    if not user:
        await create_user(
            session=session,
            telegram_id=user_id,
            telegram_username=username,
        )


@router.message(CommandStart())
async def cmd_start(
    event: Message | CallbackQuery, session: AsyncSession, redis: Redis
):
    if isinstance(event, CallbackQuery):
        telegram_id = event.from_user.id
        message = event.message
    else:
        telegram_id = event.from_user.id
        message = event

    await check_user_exists(event, session)

    user = await get_user_by_telegram_id(session, telegram_id)

    info_raw = await redis.get(f"user:{telegram_id}:info")

    info: dict = {}

    if not info_raw and user.journal_login and user.journal_password:
        pwd = decrypt_password(user.journal_password)
        client = JournalClient(
            username=user.journal_login,
            password=pwd,
            telegram_id=telegram_id,
            redis_client=redis,
        )

        async def _background_refresh():
            try:
                await client.login()
                await update_user_info(client, telegram_id)
            except Exception as err:
                logger.exception(
                    f"Background update_user_info error for {telegram_id}: {err}"
                )
            finally:
                try:
                    await client.close()
                except Exception:
                    pass

        asyncio.create_task(_background_refresh())

        info = {}
    elif info_raw:
        info = json.loads(info_raw)
    if not user.journal_login or not user.journal_password:
        return await message.answer(text_manager.get("unauthorized"))

    info.setdefault("average_score", 0)
    info.setdefault("expired_homeworks", 0)
    info.setdefault("active_homeworks", 0)
    info.setdefault("deleted_homeworks", 0)
    info["name"] = message.from_user.first_name

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text_manager.get("homeworks_menu_button"),
                    callback_data="menu:homeworks_menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=text_manager.get("get_schedule"),
                    callback_data="menu:schedule_menu",
                ),
                InlineKeyboardButton(
                    text=text_manager.get("get_leaderboard"),
                    callback_data="menu:leaderboard_menu",
                ),
            ],
        ]
    )
    await message.answer(
        text_manager.get("start").format(**info), reply_markup=keyboard
    )


async def handle_homeworks_menu(callback: CallbackQuery, redis: Redis):
    await callback.answer()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text_manager.get("back_to_menu"), callback_data="menu:main"
                )
            ]
        ]
    )
    await callback.message.edit_text(
        text_manager.get("homeworks_menu"), reply_markup=kb
    )


@router.callback_query(F.data.startswith("menu:"))
async def handle_menu_navigation(
    callback: CallbackQuery, redis: Redis, session: AsyncSession
):
    menu_type = callback.data.split(":")
    action = menu_type[1] if len(menu_type) > 1 else "menu"

    await callback.answer()
    if action == "homeworks_menu":
        await handle_homeworks_menu(callback, redis)
    elif action == "schedule_menu":
        await get_schedule(callback, redis)
    elif action == "leaderboard_menu":
        await get_leaderboard(callback, redis)
    elif action == "main":
        await cmd_start(callback, session, redis)
    else:
        message = callback.message
        user_id = callback.message.from_user.id
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text_manager.get("get_expired_homeworks"),
                    callback_data="get_expired",
                )
            ][
                InlineKeyboardButton(
                    text=text_manager.get("back_to_menu"), callback_data="menu:main"
                )
            ]
        ]
    )
    stats = await get_user_homeworks_stats(user_id, session)

    await message.edit_text(
        text_manager.get("homeworks_menu").format(**stats),
        reply_markup=kb,
    )
