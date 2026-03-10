from app.config import config
from app.text import text_manager

from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

from app.database.postgres import session_maker


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session: session_maker):
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
        data["redis"] = self.redis  # Вот теперь aiogram увидит аргумент 'redis'
        return await handler(event, data)
