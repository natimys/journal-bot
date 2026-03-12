from app.config import config
from app.text import text_manager
from app.database.redis import Redis
from app.crud import get_user_by_telegram_id
from app.states import LoginStates

from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        if isinstance(event, Message) and event.text:
            if event.text.startswith(("/start")):
                return await handler(event, data)
        
        session = data["session"]
        user = await get_user_by_telegram_id(session, event.from_user.id)

        state = data.get("state")
        current_state = await state.get_state()
        
        if current_state in [LoginStates.waiting_for_login, LoginStates.waiting_for_password]:
            return await handler(event, data)
        
        if not user or not user.journal_login:
            text = text_manager.get("auth_required")
            if isinstance(event, Message):
                await event.answer(text, parse_mode="Markdown")
            else:
                await event.answer(text, show_alert=True)
            return

        data["user"] = user
        return await handler(event, data)
    
class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis, limit: int = 500):
        self.redis = redis
        self.limit = limit

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id
        key = f"throttle:{user_id}"

        check = await self.redis.get(key)
        if check:
            await event.answer(text_manager.get("too_many_requests"))
            return
        await self.redis.set(key, "locked", px=int(self.limit))

        return await handler(event, data)


class WhitelistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            if event.from_user.id not in config.LIST:
                return await event.answer(text_manager.get("no_access"))

        return await handler(event, data)


class BlacklistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            if event.from_user.id in config.LIST:
                return await event.answer(text_manager.get("blocked"))

        return await handler(event, data)
