import asyncio
import json

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import create_user, get_user_by_telegram_id
from app.database.redis import Redis
from app.handlers.getters import get_leaderboard
from app.handlers.schedule import handle_schedule_menu
from app.handlers.homeworks import get_homeworks_keyboard, handle_homeworks_menu
from app.journal_api import JournalClient
from app.logger import logger
from app.security import decrypt_password
from app.services.cache import update_user_info
from app.text import text_manager

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


async def run_background_update(user, telegram_id, redis):
    """фоновая задача обновляющая инфу о пользователе"""

    logger.info(f"!!! Background task STARTED for {telegram_id}")
    lock_key = f"lock:update:{telegram_id}"
    await redis.set(lock_key, "1", ex=300)

    pwd = decrypt_password(user.journal_password)
    client = JournalClient(
        username=user.journal_login,
        password=pwd,
        telegram_id=telegram_id,
        redis_client=redis,
    )
    try:
        logger.info(f"!!! Attempting login for {user.journal_login}")
        await client.login()
        logger.info("!!! Login success, starting update_user_info")
        await update_user_info(client, telegram_id)
        logger.info("!!! Update FINISHED")
    except Exception as err:
        logger.error(f"Background update error for {telegram_id}: {err}")
    finally:
        await client.close()


@router.message(CommandStart())
@router.callback_query(F.data == "menu:main")
async def cmd_start(
    event: Message | CallbackQuery, session: AsyncSession, redis: Redis
):
    telegram_id = event.from_user.id
    message = event.message if isinstance(event, CallbackQuery) else event

    await check_user_exists(event, session)

    user = await get_user_by_telegram_id(session, telegram_id)
    if not user or not user.journal_login or not user.journal_password:
        return await message.answer(text_manager.get("unauthorized"))

    info_raw = await redis.get(f"user:{telegram_id}:info")
    lock_key = f"lock:update:{telegram_id}"
    is_updating = await redis.get(lock_key)

    has_info = info_raw is not None
    in_progress = is_updating is not None

    logger.info(
        f"CHECK: user={telegram_id} | has_info={has_info} | in_progress={in_progress}"
    )

    if not has_info and not in_progress:
        logger.info(f"!!! STARTING TASK !!! user_id: {telegram_id}")
        asyncio.create_task(run_background_update(user, telegram_id, redis))
        info = {}
    elif has_info:
        info = json.loads(
            info_raw.decode() if isinstance(info_raw, bytes) else info_raw
        )
        logger.info(f"!!! INFO LOADED FROM CACHE !!! user_id: {telegram_id}")
    else:
        logger.info(f"!!! TASK ALREADY IN PROGRESS !!! user_id: {telegram_id}")
        info = {}

    info.setdefault("average_score", text_manager.get("loading"))
    info.setdefault("average_attendance", text_manager.get("loading"))
    info["name"] = event.from_user.first_name

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text_manager.get("homeworks_menu_button"),
                    callback_data="menu:homeworks_menu",
                )
            ],
            [
                InlineKeyboardButton(
                    text=text_manager.get("schedule_menu_button"),
                    callback_data="menu:schedule_menu",
                ),
                InlineKeyboardButton(
                    text=text_manager.get("get_leaderboard"),
                    callback_data="menu:leaderboard_menu",
                ),
            ],
        ]
    )

    if isinstance(event, CallbackQuery):
        await event.answer()
        await message.edit_text(
            text_manager.get("start").format(**info), reply_markup=keyboard
        )
    else:
        await message.answer(
            text_manager.get("start").format(**info), reply_markup=keyboard
        )


@router.callback_query(F.data.startswith("menu:"))
async def handle_menu_navigation(
    callback: CallbackQuery, redis: Redis, session: AsyncSession
):
    parts = callback.data.split(":")
    action = parts[1] if len(parts) > 1 else "main"

    if action == "main":
        return await cmd_start(callback, session, redis)
    elif action == "homeworks_menu":
        return await handle_homeworks_menu(callback, redis)

    elif action == "hw_list":
        status = int(parts[2])
        kb = await get_homeworks_keyboard(callback.from_user.id, redis, status, page=0)
        if not kb:
            return await callback.answer(
                text_manager.get("homeworks_empty"), show_alert=True
            )

        titles = {
            0: text_manager.get("homeworks_expired"),
            3: text_manager.get("homeworks_active"),
            5: text_manager.get("homeworks_deleted"),
        }
        header = titles.get(status, text_manager.get("status_default"))
        await callback.message.edit_text(
            f"📚 {titles.get(status, header)}:", reply_markup=kb
        )
        return

    elif action == "schedule_menu":
        return await handle_schedule_menu(callback)
    elif action == "leaderboard_menu":
        return await get_leaderboard(callback, redis)

    await callback.answer("Раздел в разработке 🚧")
