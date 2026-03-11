from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User


async def get_user_by_id(session: AsyncSession, id: int):
    result = await session.execute(select(User).where(User.id == id))
    return result.scalars().first()


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int):
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalars().first()


async def create_user(session: AsyncSession, telegram_id: int, telegram_username: str, **kwargs):
    new_user = User(
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        **kwargs
    )
    session.add(new_user)
    await session.commit()
    return new_user
