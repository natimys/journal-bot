from app.config import config
from app.text import text_manager

from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

whitelist_str = config["WHITELIST"]
whitelist_set = {int(uid.strip()) for uid in whitelist_str.split(",") if uid.strip()}

class WhitelistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            if event.from_user.id not in whitelist_set:
                return await event.answer(text_manager.get("no_access"))
        
        return await handler(event, data)