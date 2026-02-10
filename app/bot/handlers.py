import logging

from aiogram import Router, types
from aiogram.filters import CommandStart

from app.db.supabase import get_supabase_client

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    logger.info("Received /start from chat_id=%s", chat_id)

    try:
        db = get_supabase_client()
        db.table("users").upsert({"id": chat_id}).execute()
        logger.info("User %s saved to DB", chat_id)
    except Exception as exc:
        logger.error("Failed to upsert user %s: %s", chat_id, exc)

    await message.answer("Бот работает! Жду новостей...")
