from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

from app.text import text_manager
from app.crud import get_user_by_telegram_id, create_user


router = Router()


async def check_user_exists(message: Message, session: AsyncSession):
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await create_user(
            session=session,
            telegram_id=message.from_user.id,
            telegram_username=message.from_user.first_name,
        )


async def get_user_homeworks_stats(telegram_id, session: AsyncSession):
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        return {
            "expired_count": 0,
            "active_count": 0,
            "deleted_count": 0,
        }


async def get_user_info(telegram_id, session: AsyncSession):
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        return {
            "name": user.telegram_username,
            "average_score": 5,
            "lessons_count": 4,
        }


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    builder = InlineKeyboardBuilder()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text_manager.get("get_homeworks"),
                    callback_data="menu_homework",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=text_manager.get("get_schedule"), callback_data="get_schedule"
                ),
                InlineKeyboardButton(
                    text=text_manager.get("get_leaderboard"),
                    callback_data="get_leaderboard",
                ),
            ],
        ]
    )
    await check_user_exists(message, session)
    info = await get_user_info(message.from_user.id, session)
    await message.answer(
        text_manager.get("start").format(**info), reply_markup=keyboard
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(text_manager.get("help"))


@router.callback_query(F.data == "menu_homework")
@router.message(Command("homework"))
async def homeworks(event: Message | CallbackQuery, session: AsyncSession):
    if isinstance(event, CallbackQuery):
        await event.answer()
        message = event.message
        user_id = event.from_user.id
    else:
        message = event
        user_id = event.from_user.id
    back_to_menu_button = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="menu")]]
    )
    stats = await get_user_homeworks_stats(user_id, session)

    await message.edit_text(
        text_manager.get("menu_homework").format(**stats),
        reply_markup=back_to_menu_button,
    )


@router.callback_query(F.data == "menu")
async def start_menu(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    await cmd_start(callback.message, session)
