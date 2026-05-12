import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import (
    InlineKeyboardBuilder,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from redis.asyncio import Redis

from app.services.user import get_labworks_keyboard, get_user_labworks_stats
from app.states import HomeworkUpload
from app.text import text_manager

router = Router()


async def handle_labworks_menu(callback: CallbackQuery, redis: Redis):
    """Меню со статистикой лабораторных"""
    await callback.answer()
    stats = await get_user_labworks_stats(callback.from_user.id, redis)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🔴 {text_manager.get('homeworks_expired')}",
                    callback_data="menu:lw_list:0",
                ),
                InlineKeyboardButton(
                    text=f"🟢 {text_manager.get('homeworks_active')}",
                    callback_data="menu:lw_list:3",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"⚪ {text_manager.get('homeworks_deleted')}",
                    callback_data="menu:lw_list:5",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=text_manager.get("back_to_menu"), callback_data="menu:main"
                )
            ],
        ]
    )
    await callback.message.edit_text(
        text_manager.get("labworks_menu").format(**stats), reply_markup=kb
    )


@router.callback_query(F.data.startswith("lw_page:"))
async def handle_lw_pagination(callback: CallbackQuery, redis: Redis):
    parts = callback.data.split(":")
    status = int(parts[1])
    page = int(parts[2])

    kb = await get_labworks_keyboard(callback.from_user.id, redis, status, page=page)
    if kb:
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("lw_view:"))
async def handle_lw_view(callback: CallbackQuery, redis: Redis):
    hw_id = callback.data.split(":")[1]

    raw_data = await redis.get(f"hw:content:{hw_id}")
    if not raw_data:
        return await callback.answer(
            text_manager.get("homeworks_not_found"), show_alert=True
        )

    hw = json.loads(raw_data)

    text = (
        f"📖 <b>{hw.get('subject')}</b>\n"
        f"{text_manager.get('teacher')} {hw.get('teacher')}\n"
        f"{text_manager.get('expires_at')} {hw.get('overdue_time', 'no')}\n\n"
        f"{text_manager.get('subject')} {hw.get('description')}\n"
    )

    if hw.get("comment"):
        text += f"\n{text_manager.get('comment')} {hw.get('comment')}"

    builder = InlineKeyboardBuilder()

    if hw.get("file_url"):
        builder.row(
            InlineKeyboardButton(
                text=text_manager.get("download_homework"), url=hw.get("file_url")
            )
        )
    builder.row(
        InlineKeyboardButton(
            text=text_manager.get("upload_homework"), callback_data=f"lw_upload:{hw_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=text_manager.get("back_to_menu"), callback_data="menu:labworks_menu"
        )
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("lw_upload:"))
async def start_labwork_upload(callback: CallbackQuery, state: FSMContext):
    hw_id = callback.data.split(":")[1]

    await state.update_data(hw_id=hw_id, files=[], return_to="menu:labworks_menu")

    await state.set_state(HomeworkUpload.waiting_for_files)

    await callback.message.edit_text(
        text_manager.get("uploading_homework_menu"),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=text_manager.get("send_homework"),
                        callback_data="hw_submit",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=text_manager.get("undo_homework"),
                        callback_data="menu:labworks_menu",
                    )
                ],
            ]
        ),
    )
    await callback.answer()
