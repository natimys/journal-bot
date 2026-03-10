from aiogram import Router
from aiogram.filters import  Command
from aiogram.types import Message
from app.text import text_manager
from app.req import Session

router = Router()

@router.message(Command("login"))
async def login(message: Message):
    last_message = message.text.split()
    # пока что для входа треубется /login login pass, нужно переделать под отдельное меню + шифровать то что в бд попадает
    login = last_message[1]
    password = last_message[2]
    session = Session(login, password)
    try:
        await session.login()
        await message.answer("login успешен!")
    except Exception as e:
        await message.answer("произошла ошибка")