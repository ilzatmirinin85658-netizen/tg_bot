import logging

from aiogram import Router, types
from aiogram.filters import Command, CommandStart

from app.db.supabase import get_supabase_client
from app.services.parser import fetch_and_process_rss

logger = logging.getLogger(__name__)

router = Router()

RSS_URL = "https://habr.com/ru/rss/hubs/python/"

# In-memory activity flag (survives until redeploy)
bot_active = True


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


@router.message(Command("sleep"))
async def cmd_sleep(message: types.Message):
    global bot_active
    bot_active = False
    logger.info("Bot set to SLEEP by chat_id=%s", message.chat.id)
    await message.answer("\U0001f4a4 Ушел в спящий режим. Парсинг и рассылка приостановлены. GN!")


@router.message(Command("wake"))
async def cmd_wake(message: types.Message):
    global bot_active
    bot_active = True
    logger.info("Bot set to WAKE by chat_id=%s", message.chat.id)
    await message.answer("\u2600\ufe0f GM! Возвращаюсь к работе.")


@router.message(Command("check_now"))
async def cmd_check_now(message: types.Message):
    logger.info("Received /check_now from chat_id=%s", message.chat.id)
    await message.answer("\U0001f50d Запускаю внеочередной поиск новостей...")

    try:
        saved = await fetch_and_process_rss(RSS_URL)
    except Exception as exc:
        logger.error("/check_now parse error: %s", exc)
        await message.answer(f"Ошибка при парсинге: {exc}")
        return

    if saved > 0:
        # Send new articles to all users right away
        bot = message.bot
        db = get_supabase_client()
        users = db.table("users").select("id").execute()
        rows = (
            db.table("articles")
            .select("*")
            .eq("is_sent", False)
            .order("created_at")
            .execute()
        )
        for article in rows.data:
            text = (
                f"<b>{article['title']}</b>\n\n"
                f"{article.get('summary') or ''}\n\n"
                f"Score: {article.get('ai_score', '?')}/10\n"
                f"{article['url']}"
            )
            for user in users.data:
                try:
                    await bot.send_message(user["id"], text, parse_mode="HTML")
                except Exception as exc:
                    logger.error("Failed to send to %s: %s", user["id"], exc)

            db.table("articles").update({"is_sent": True}).eq(
                "id", article["id"]
            ).execute()

    await message.answer(f"Проверка завершена. Найдено новых статей: {saved}")
