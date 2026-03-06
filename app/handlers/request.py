from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from curl_cffi.requests.exceptions import DNSError
from app.req import session
from app.logger import logger

router = Router(name="Router that works with requests")


@router.message(Command("get_schedule"))
async def cmd_get_schedule(message: Message):
    try:
        schedule = await session.get_current_schedule()
    except DNSError:
        await message.answer("❌ Возникла ошибка на стороне сервера, повторите попытку позже") 
    else:
        lines = [
            f"{i}. {item['started_at']} - {item["finished_at"]} | {item['subject_name'].removesuffix(" (РПО)")}"
            for i, item in enumerate(schedule, 1)
        ]
        text = "\n".join(lines)
        logger.info(f"get_schedule called, responsed to @{message.from_user.username}")
        await message.answer(text)


@router.message(Command("get_leaderboard"))
async def cmd_get_leaderboard(message: Message):
    leaderboard = await session.get_leaderboard()
    lines = [
        f"{i}. {item['full_name']} - {item['amount']} очков"
        for i, item in enumerate(leaderboard, 1)
    ]
    text = "\n".join(lines)
    logger.info(f"get_leaderboard called, responsed to @{message.from_user.username}")
    await message.answer(text)