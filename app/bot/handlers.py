import logging

from aiogram import Router, types
from aiogram.filters import CommandStart

logger = logging.getLogger(__name__)

router = Router()

# Store chat IDs of users who started the bot
active_chats: set[int] = set()


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    active_chats.add(chat_id)
    logger.info("Received /start from chat_id=%s", chat_id)
    await message.answer("Бот работает! Жду новостей...")
