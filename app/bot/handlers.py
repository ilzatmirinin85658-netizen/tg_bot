import logging

from aiogram import Router, types
from aiogram.filters import Command, CommandStart

from app.core.config import settings
from app.db.supabase import get_supabase_client
from app.services.parser import fetch_and_process_rss

logger = logging.getLogger(__name__)

router = Router()

RSS_URL = "https://habr.com/ru/rss/hubs/python/"

# In-memory activity flag (survives until redeploy)
bot_active = True


def _is_admin(message: types.Message) -> bool:
    return message.from_user and message.from_user.id == settings.ADMIN_ID


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

    await message.answer("\u0411\u043e\u0442 \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442! \u0416\u0434\u0443 \u043d\u043e\u0432\u043e\u0441\u0442\u0435\u0439...")


@router.message(Command("sleep"))
async def cmd_sleep(message: types.Message):
    if not _is_admin(message):
        await message.answer("\u041d\u0435\u0442 \u043f\u0440\u0430\u0432 \u0434\u043b\u044f \u044d\u0442\u043e\u0439 \u043a\u043e\u043c\u0430\u043d\u0434\u044b.")
        return
    global bot_active
    bot_active = False
    logger.info("Bot set to SLEEP by chat_id=%s", message.chat.id)
    await message.answer("\U0001f4a4 \u0423\u0448\u0435\u043b \u0432 \u0441\u043f\u044f\u0449\u0438\u0439 \u0440\u0435\u0436\u0438\u043c. \u041f\u0430\u0440\u0441\u0438\u043d\u0433 \u0438 \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0430 \u043f\u0440\u0438\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u044b. GN!")


@router.message(Command("wake"))
async def cmd_wake(message: types.Message):
    if not _is_admin(message):
        await message.answer("\u041d\u0435\u0442 \u043f\u0440\u0430\u0432 \u0434\u043b\u044f \u044d\u0442\u043e\u0439 \u043a\u043e\u043c\u0430\u043d\u0434\u044b.")
        return
    global bot_active
    bot_active = True
    logger.info("Bot set to WAKE by chat_id=%s", message.chat.id)
    await message.answer("\u2600\ufe0f GM! \u0412\u043e\u0437\u0432\u0440\u0430\u0449\u0430\u044e\u0441\u044c \u043a \u0440\u0430\u0431\u043e\u0442\u0435.")


@router.message(Command("check_now"))
async def cmd_check_now(message: types.Message):
    """Admin-only: trigger the Hunter (parser) immediately.
    Does NOT send articles — Publisher handles that on its own schedule.
    """
    if not _is_admin(message):
        await message.answer("\u041d\u0435\u0442 \u043f\u0440\u0430\u0432 \u0434\u043b\u044f \u044d\u0442\u043e\u0439 \u043a\u043e\u043c\u0430\u043d\u0434\u044b.")
        return
    logger.info("Received /check_now from chat_id=%s", message.chat.id)
    await message.answer("\U0001f50d \u0417\u0430\u043f\u0443\u0441\u043a\u0430\u044e \u0432\u043d\u0435\u043e\u0447\u0435\u0440\u0435\u0434\u043d\u043e\u0439 \u043f\u043e\u0438\u0441\u043a \u043d\u043e\u0432\u043e\u0441\u0442\u0435\u0439...")

    try:
        saved = await fetch_and_process_rss(RSS_URL)
    except Exception as exc:
        logger.error("/check_now parse error: %s", exc)
        await message.answer(f"\u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u0440\u0438 \u043f\u0430\u0440\u0441\u0438\u043d\u0433\u0435: {exc}")
        return

    await message.answer(
        f"\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0430. \u041d\u043e\u0432\u044b\u0445 \u0441\u0442\u0430\u0442\u0435\u0439 \u0441 score \u2265 7: {saved}\n"
        "\u041f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u044f \u043f\u043e \u0440\u0430\u0441\u043f\u0438\u0441\u0430\u043d\u0438\u044e (Publisher \u043a\u0430\u0436\u0434\u044b\u0435 4\u0447)."
    )
