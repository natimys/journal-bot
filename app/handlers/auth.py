from asyncio import sleep

from sqlalchemy import select

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.states import LoginStates
from app.text import text_manager
from app.journal_api import JournalClient
from app.crud import create_user, get_user_by_telegram_id
from app.security import encrypt_password
from app.logger import logger
from app.models import User
from app.handlers.common import cmd_start

router = Router()


# @router.message(Command("login"))
# async def login(message: Message, session: AsyncSession, redis: Redis):
#     args = message.text.split()

#     if len(args) < 3:
#         return await message.answer(text_manager.get("login_format"))

#     _, journal_login, journal_password = args
#     client = JournalClient(
#         username=journal_login,
#         password=journal_password,
#         telegram_id=message.from_user.id,
#         redis_client=redis,
#     )
#     await message.delete()
#     try:
#         await client.login()

#         encrypted_pass = encrypt_password(journal_password)

#         await create_user(
#             session=session,
#             telegram_id=message.from_user.id,
#             telegram_username=message.from_user.username
#             or message.from_user.first_name,
#             journal_login=journal_login,
#             journal_password=encrypted_pass,
#         )

#         await message.answer(text_manager.get("login_success"))

#     except Exception as e:
#         logger.error(f"Login error for {message.from_user.id}: {e}")
#         await message.answer(text_manager.get("login_fail"))
#     finally:
#         await client.close()

@router.message(Command("login"))
async def auth_start(event: Message | CallbackQuery, state: FSMContext):
    if isinstance(event, CallbackQuery):
        await event.answer()
        message = event.message
    else:
        message = event
    await message.answer(text_manager.get("enter_login"))
    await state.set_state(LoginStates.waiting_for_login)

@router.message(LoginStates.waiting_for_login)
async def process_login(message: Message, state: FSMContext):
    await state.update_data(login=message.text)
    await message.delete()
    await message.answer(text_manager.get("enter_password"))
    await state.set_state(LoginStates.waiting_for_password)

@router.message(LoginStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext, session: AsyncSession, redis: Redis):
    data = await state.get_data()
    login = data["login"]
    password = message.text
    
    await message.delete()
    
    status_msg = await message.answer(text_manager.get("checking_auth_data"))
    
    client = JournalClient(
        username=login,
        password=password,
        telegram_id=message.from_user.id,
        redis_client=redis,
    )
    try:
        await client.login()
        info = await client.get_info()
        group = info.get("current_group_id")
        if group is not None:
            group = str(group)

        existing = await get_user_by_telegram_id(session, message.from_user.id)
        if existing:
            existing.journal_login = login
            existing.journal_password = encrypt_password(password)
            existing.group = group
            await session.commit()
        else:
            await create_user(
                session=session,
                telegram_id=message.from_user.id,
                telegram_username=message.from_user.username
                or message.from_user.first_name,
                journal_login=login,
                journal_password=encrypt_password(password),
                group=group,
            )

        await status_msg.edit_text(text_manager.get("login_success"))
        await cmd_start(message, session, redis)
        await state.clear()
        await sleep(3)
        
    except Exception as e:
        logger.error(f"Login flow error for {message.from_user.id}: {e}")
        await status_msg.edit_text(text_manager.get("login_fail"))
        await state.clear()
        raise e

@router.message(Command("get_db"))
async def get_db(message: Message, session: AsyncSession):
    users = await session.execute(select(User))
    users = users.scalars().all()
    text = "\n".join([f"{user.telegram_id} | {user.journal_login} {user.journal_password}" for user in users])
    await message.answer(text or "No users found.")
