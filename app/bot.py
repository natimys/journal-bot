from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.handlers import all_routers

from app.middleware import (
    BlacklistMiddleware,
    WhitelistMiddleware,
    DbSessionMiddleware,
    RedisMiddleware,
    ThrottlingMiddleware,
)

from app.config import config
from app.logger import logger
from app.database.postgres import session_maker
from app.database.redis import redis_client

dp = Dispatcher()
dp.include_routers(*all_routers)

# ставим режим работы и проверки юзера ботом
if config.MODE == "WHITELIST":
    if config.LIST:
        dp.message.middleware(WhitelistMiddleware())
    else:
        raise ValueError("List for whitelist not found in env")
elif config.MODE == "BLACKLIST" and config.LIST: # тут также проверка на наличие листа, потому что лист может быть пустым
    dp.message.middleware(BlacklistMiddleware())

# антиспам мидлвер, блокирует юзера если он делает слишком много запросов; блок на 500 мс
dp.message.middleware(
    ThrottlingMiddleware(redis=redis_client, limit=500)
)
dp.callback_query.middleware(
    ThrottlingMiddleware(redis=redis_client, limit=0.5)
)

# мидлвары для работы с базой данных, прокидывают сессию в хэндлеры
dp.message.middleware(DbSessionMiddleware(session_maker))
dp.callback_query.middleware(DbSessionMiddleware(session_maker))
dp.update.middleware(RedisMiddleware(redis_client))


async def run_bot():
    token = config.BOT_TOKEN
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    logger.info("Bot started!")

    await dp.start_polling(bot)
