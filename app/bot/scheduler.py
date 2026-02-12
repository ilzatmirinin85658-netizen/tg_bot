import logging

from aiogram import Bot

from app.core.config import settings
from app.db.supabase import get_supabase_client

logger = logging.getLogger(__name__)


def _format_article(article: dict) -> str:
    meaningful = article.get("meaningful_title") or article["title"]
    summary = article.get("summary") or ""
    original_title = article["title"]
    url = article["url"]
    return (
        f"<b>{meaningful}</b>\n\n"
        f"\U0001f4d1 <b>Summary</b>\n{summary}\n\n"
        f'\U0001f517 <a href="{url}">\u041e\u0440\u0438\u0433\u0438\u043d\u0430\u043b: {original_title}</a>'
    )


async def publish_one(bot: Bot) -> bool:
    """Take the oldest unsent good article from DB and send it to all users.

    Returns True if an article was published, False if the queue was empty.
    """
    db = get_supabase_client()

    # Get all registered users
    users = db.table("users").select("id").execute()
    if not users.data:
        logger.warning("[Publisher] \u041d\u0435\u0442 \u0437\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0445 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439")
        return False

    # Get ONE oldest unsent article with score >= 7
    rows = (
        db.table("articles")
        .select("*")
        .eq("is_sent", False)
        .gte("ai_score", 7)
        .order("created_at")
        .limit(1)
        .execute()
    )
    if not rows.data:
        logger.info("[Publisher] \u041e\u0447\u0435\u0440\u0435\u0434\u044c \u043f\u0443\u0441\u0442\u0430.")
        return False

    article = rows.data[0]
    text = _format_article(article)
    logger.info(
        "[Publisher] \u041f\u0443\u0431\u043b\u0438\u043a\u0443\u044e: %s (score=%s)",
        article["title"][:60], article.get("ai_score"),
    )

    for user in users.data:
        chat_id = user["id"]
        try:
            await bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception as exc:
            logger.error("[Publisher] Failed to send to chat %s: %s", chat_id, exc)

    # Mark as sent
    db.table("articles").update({"is_sent": True}).eq(
        "id", article["id"]
    ).execute()

    logger.info("[Publisher] \u0421\u0442\u0430\u0442\u044c\u044f \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0430 \u0432 %d \u0447\u0430\u0442(\u043e\u0432).", len(users.data))
    return True
