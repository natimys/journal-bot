import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import (
    InlineKeyboardBuilder,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import get_user_by_telegram_id
from app.journal_api import JournalClient
from app.logger import logger
from app.security import decrypt_password
from app.services.archiver import create_homework_zip
from app.services.user import get_homeworks_keyboard, get_user_homeworks_stats
from app.states import HomeworkUpload
from app.text import text_manager

router = Router()


async def handle_homeworks_menu(callback: CallbackQuery, redis: Redis):
    """Меню со статистикой домашек"""
    await callback.answer()
    stats = await get_user_homeworks_stats(callback.from_user.id, redis)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🔴 {text_manager.get('homeworks_expired')}",
                    callback_data="menu:hw_list:0",
                ),
                InlineKeyboardButton(
                    text=f"🟢 {text_manager.get('homeworks_active')}",
                    callback_data="menu:hw_list:3",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"⚪ {text_manager.get('homeworks_deleted')}",
                    callback_data="menu:hw_list:5",
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
        text_manager.get("homeworks_menu").format(**stats), reply_markup=kb
    )


@router.callback_query(F.data.startswith("hw_page:"))
async def handle_hw_pagination(callback: CallbackQuery, redis: Redis):
    parts = callback.data.split(":")
    status = int(parts[1])
    page = int(parts[2])

    kb = await get_homeworks_keyboard(callback.from_user.id, redis, status, page=page)
    if kb:
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("hw_view:"))
async def handle_hw_view(callback: CallbackQuery, redis: Redis):
    hw_id = callback.data.split(":")[1]

    raw_data = await redis.get(f"hw:content:{hw_id}")
    if not raw_data:
        return await callback.answer(
            text_manager.get("homeworks_not_found"), show_alert=True
        )

    hw = json.loads(raw_data)  # hw = homework

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
            text=text_manager.get("upload_homework"), callback_data=f"hw_upload:{hw_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=text_manager.get("back_to_menu"), callback_data="menu:homeworks_menu"
        )
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("hw_upload:"))
async def start_homework_upload(callback: CallbackQuery, state: FSMContext):
    hw_id = callback.data.split(":")[1]

    await state.update_data(hw_id=hw_id, files=[])

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
                        callback_data="menu:homeworks_menu",
                    )
                ],
            ]
        ),
    )
    await callback.answer()


@router.message(HomeworkUpload.waiting_for_files, F.photo | F.document)
async def process_homework_files(message: Message, state: FSMContext):
    data = await state.get_data()
    files = data.get("files", [])

    if message.photo:
        files.append({"type": "photo", "file_id": message.photo[-1].file_id})
    elif message.document:
        files.append({"type": "doc", "file_id": message.document.file_id})

    await state.update_data(files=files)

    if not message.media_group_id:
        file_count = len(files)
        await message.reply(
            text_manager.get("file_added").format(file_count=file_count)  # noqa: F522
        )
    else:
        pass


@router.callback_query(F.data == "hw_submit")
async def handle_hw_submit(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, redis: Redis
):
    data = await state.get_data()
    file_ids = [f["file_id"] for f in data.get("files", [])]
    hw_id = data.get("hw_id")

    if not file_ids:
        return await callback.answer(
            text_manager.get("send_homework_files_first"), show_alert=True
        )

    await callback.message.edit_text(text_manager.get("archiving_files"))

    zip_buffer = await create_homework_zip(callback.bot, file_ids)

    user = await get_user_by_telegram_id(session, callback.from_user.id)
    pwd = decrypt_password(user.journal_password)
    client = JournalClient(user.journal_login, pwd, user.telegram_id, redis)

    try:
        await callback.message.edit_text(
            text_manager.get("sending_homeworks_to_journal")
        )

        filename = f"homework_{hw_id}.zip"

        result = await client.upload_homework(
            zip_data=zip_buffer, filename=filename, homework_id=int(hw_id)
        )

        logger.info(f"Full upload cycle finished: {result}")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=text_manager.get("back_to_menu"),
                        callback_data="menu:homeworks_menu",
                    )
                ]
            ]
        )
        await callback.message.edit_text(
            text_manager.get("homework_send_success"), reply_markup=kb
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        await callback.message.edit_text(
            text_manager.get("homework_send_error".format(error=str(e)))  # noqa: F522
        )
    finally:
        await client.close()
