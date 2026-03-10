from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from app.text import text_manager
from app.crud import get_user_by_telegram_id, create_user


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    user = await get_user_by_telegram_id(session, message.from_user.id)

    if not user:
        await create_user(session, message.from_user.id, message.from_user.first_name)


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(text_manager.get("help"))
