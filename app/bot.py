from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.handlers import all_routers

from app.middleware import WhitelistMiddleware, DbSessionMiddleware, RedisMiddleware

from app.config import config
from app.logger import logger
from app.database.postgres import session_maker
from app.database.redis import redis_client

dp = Dispatcher()
dp.include_routers(*all_routers)

dp.message.middleware(WhitelistMiddleware())
dp.message.middleware(DbSessionMiddleware(session_maker))
dp.update.middleware(RedisMiddleware(redis_client))

async def run_bot():
    token = config.BOT_TOKEN
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    logger.info("Bot started!")

    await dp.start_polling(bot)
