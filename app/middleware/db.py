from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.text import text_manager
from app.config import config
from app.database.postgres import session_maker


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self.session() as session:
            data["session"] = session
            return await handler(event, data)

class RedisMiddleware(BaseMiddleware):
    def __init__(self, redis):
        self.redis = redis

    async def __call__(self, handler, event, data):
        data["redis"] = self.redis
        return await handler(event, data)
