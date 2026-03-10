from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.handlers.common import router as common_router
from app.handlers.request import router as request_router
from app.handlers.auth import router as auth_router

from app.middleware.whitelist import WhitelistMiddleware

from app.config import config
from app.logger import logger

dp = Dispatcher()
dp.include_router(common_router)
dp.include_router(request_router)
dp.include_router(auth_router)

dp.message.middleware(WhitelistMiddleware())

@logger.log_with_timer()
async def run_bot():
    token = config.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN is not set in config")
    bot = Bot(token=token, 
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    logger.info("Bot started!")
    
    await dp.start_polling(bot)