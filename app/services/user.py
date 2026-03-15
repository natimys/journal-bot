import json

from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardButton, InlineKeyboardBuilder

from app.database.redis import Redis

async def get_user_homeworks_stats(telegram_id: int, redis: Redis):
    raw = await redis.get(f"user:{telegram_id}:info")
    if raw:
        data = json.loads(raw)
        return {
            "expired_count": data.get("expired_count", 0),
            "active_count": data.get("active_count", 0),
            "deleted_count": data.get("deleted_count", 0),
            "average_score": data.get("average_score", 0)
        }
    
    return {"expired_count": 0, "active_count": 0, "deleted_count": 0, "average_score": 0}


async def get_user_info(message: Message, redis: Redis):
    return {
        "name": message.from_user.username,
        "average_score": 5,
        "lessons_count": 4,
    }

async def get_homeworks_keyboard(telegram_id: int, redis: Redis, status: int, page: int = 0):
    """Генерирует клавиатуру со списком ДЗ для конкретного статуса и страницы"""
    
    raw_data = await redis.get(f"user:{telegram_id}:homeworks_full")
    if not raw_data:
        return None
    
    all_homeworks = json.loads(raw_data)
    hw_list = all_homeworks.get(str(status), [])
    
    if not hw_list:
        return None

    per_page = 5
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_page_items = hw_list[start_idx:end_idx]
    total_pages = (len(hw_list) - 1) // per_page + 1

    builder = InlineKeyboardBuilder()

    for hw in current_page_items:
        btn_text = f"{hw['subject'][:18]} - {hw['date_limit']}"
        builder.row(InlineKeyboardButton(text=btn_text, callback_data=f"hw_view:{hw['id']}"))

    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton(text="⬅️", callback_data=f"hw_page:{status}:{page-1}"))
    
    nav_btns.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    
    if end_idx < len(hw_list):
        nav_btns.append(InlineKeyboardButton(text="➡️", callback_data=f"hw_page:{status}:{page+1}"))
    
    builder.row(*nav_btns)
    
    builder.row(InlineKeyboardButton(text="🔙 Назад к статистике", callback_data="menu:homeworks_menu"))
    
    return builder.as_markup()