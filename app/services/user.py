from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.journal_api import JournalClient
from app.database.redis import Redis
from app.crud import get_user_by_telegram_id
from app.constants import GET_HOMEWORKS_URL

async def get_user_homeworks_stats(message: Message, redis: Redis, session: AsyncSession):
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if user:
        client = JournalClient(
            username=user.journal_login,
            password=user.journal_password,
            telegram_id=message.from_user.id,
            redis_client=redis
        )
        client._make_request(GET_HOMEWORKS_URL.format())
    return {
        "expired_count": 0,
        "active_count": 0,
        "deleted_count": 0,
    }


async def get_user_info(message: Message, redis: Redis):
    return {
        "name": message.from_user.username,
        "average_score": 5,
        "lessons_count": 4,
    }
