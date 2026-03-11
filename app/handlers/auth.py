from sqlalchemy import select

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.text import text_manager
from app.journal_api import JournalClient
from app.crud import create_user
from app.security import encrypt_password
from app.logger import logger
from app.models import User

router = Router()


@router.message(Command("login"))
async def login(message: Message, session: AsyncSession, redis: Redis):
    args = message.text.split()

    if len(args) < 3:
        return await message.answer(text_manager.get("login_format"))

    _, journal_login, journal_password = args
    client = JournalClient(
        username=journal_login,
        password=journal_password,
        telegram_id=message.from_user.id,
        redis_client=redis,
    )
    await message.delete()
    try:
        await client.login()

        encrypted_pass = encrypt_password(journal_password)

        await create_user(
            session=session,
            telegram_id=message.from_user.id,
            telegram_username=message.from_user.username
            or message.from_user.first_name,
            journal_login=journal_login,
            journal_password=encrypted_pass,
        )

        await message.answer(text_manager.get("login_success"))

    except Exception as e:
        logger.error(f"Login error for {message.from_user.id}: {e}")
        await message.answer(text_manager.get("login_fail"))
    finally:
        await client.close()


@router.message(Command("get_db"))
async def get_db(message: Message, session: AsyncSession):
    users = await session.execute(select(User))
    users = users.scalars().all()
    text = "\n".join([f"{user.telegram_id} | {user.journal_login} {user.journal_password}" for user in users])
    await message.answer(text or "No users found.")
