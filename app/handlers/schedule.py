from collections import defaultdict
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import get_user_by_telegram_id
from app.journal_api import JournalClient  # твой клиент
from app.logger import logger
from app.security import decrypt_password
from app.services.cache import get_cached_schedule_date, get_cached_schedule_range
from app.text import text_manager

router = Router()


# @router.callback_query(F.data == "menu:schedule_menu")
async def handle_schedule_menu(callback: CallbackQuery):
    """Отображение меню выбора дня"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=text_manager.get('get_schedule_today'), callback_data="schedule:today"),
                InlineKeyboardButton(text=text_manager.get('get_schedule_tomorrow'), callback_data="schedule:tomorrow"),
            ],
            [
                InlineKeyboardButton(text=text_manager.get('get_schedule_week'), callback_data="schedule:week"),
            ],
            [
                InlineKeyboardButton(text=text_manager.get("back_to_menu"), callback_data="menu:main")
            ],
        ]
    )
    await callback.message.edit_text(text_manager.get("schedule_menu_title"), reply_markup=kb)


@router.callback_query(F.data.startswith("schedule:"))
async def handle_schedule_action(callback: CallbackQuery, redis: Redis, session: AsyncSession):
    await callback.answer()

    action = callback.data.split(":")[1]
    user = await get_user_by_telegram_id(session, callback.from_user.id)

    if not user or not user.group:
        await callback.message.answer(text_manager.get("group_not_found"))
        return

    if not callback.message:
        return

    await callback.message.edit_text(text_manager.get('loading'))

    real_password = decrypt_password(user.journal_password)

    client = JournalClient(
        username=user.journal_login,
        password=real_password,
        telegram_id=user.telegram_id,
        redis_client=redis
    )

    try:
        schedule_data = []
        title = ""

        if action == "week":
            title = text_manager.get('schedule_week') + "\n\n"
            schedule_data = await get_cached_schedule_range(client, user.group)
        else:
            target_date = datetime.now()
            if action == "tomorrow":
                target_date += timedelta(days=1)

            date_str = target_date.strftime("%Y-%m-%d")
            day_name_key = "schedule_tomorrow" if action == "tomorrow" else "schedule_today_label"
            title = text_manager.get(day_name_key) + f"\n({date_str})\n\n"

            raw_data = await get_cached_schedule_date(client, user.group, date_str)
            schedule_data = raw_data if isinstance(raw_data, list) else []

        if not schedule_data:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text=text_manager.get("back_to_menu"), callback_data="menu:schedule_menu")
                    ],
                ]
            )
            await callback.message.edit_text(text_manager.get('schedule_empty'), reply_markup=kb)
            return

        schedule_data.sort(key=lambda x: (x.get("date", ""), x.get("started_at", "")))

        days_schedule = defaultdict(list)

        for item in schedule_data:
            date_str = item.get("date", "")
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                weekday_idx = date_obj.weekday()
                weekday_name = text_manager.get(f"wd_{weekday_idx}")
                display_header = text_manager.get(
                    "schedule_day_header",
                    weekday_name=weekday_name,
                    date=date_obj.strftime("%d.%m")
                )
            except ValueError:
                display_header = f"🗓 <b>Дата: {date_str}</b>"

            days_schedule[display_header].append(item)

        response_text = title

        for day_header, lessons in days_schedule.items():
            response_text += f"{day_header}\n"
            for lesson in lessons:
                start = lesson.get("started_at", "??")[:5]
                end = lesson.get("finished_at", "??")[:5]
                subject = lesson.get("subject_name", "Предмет неизвестен")

                response_text += f"⏰ <b>{start} — {end}</b> | {subject}\n"

            response_text += "\n"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=text_manager.get("back_to_menu"), callback_data="menu:schedule_menu")
                ],
            ]
        )
        await callback.message.edit_text(response_text.strip(), reply_markup=kb)

    except Exception as e:
        logger.error(f"Schedule fetch error: {e}")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=text_manager.get("back_to_menu"), callback_data="menu:main")
                ],
            ]
        )
        await callback.message.edit_text(text_manager.get("get_schedule_error"), reply_markup=kb)
    finally:
        await client.close()
