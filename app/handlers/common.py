from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from app.text import text_manager


router = Router(name="__name__")

@router.message(CommandStart())
async def cmd_start(message: Message):
    print(f"ответил @{message.from_user.username}")
    await message.answer(text_manager.get("start"))

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(text_manager.get("help"))
    