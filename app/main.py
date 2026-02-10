import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from pydantic import BaseModel

from app.bot.handlers import active_chats, router
from app.core.config import settings
from app.db.supabase import get_supabase_client
from app.services.ai_service import AIAnalyzer
from app.services.parser import fetch_and_process_rss

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

RSS_URL = "https://habr.com/ru/rss/hubs/python/"

bot = Bot(token=settings.TELEGRAM_TOKEN)
dp = Dispatcher()
dp.include_router(router)
logger.info("Router registered, handlers: %s", [h.callback.__name__ for h in router.message.handlers])

analyzer = AIAnalyzer()
scheduler = AsyncIOScheduler()


async def scheduled_parse():
    """Periodic RSS parsing task."""
    logger.info("Running scheduled RSS parse...")
    try:
        saved = await fetch_and_process_rss(RSS_URL)
        logger.info("RSS parse done, saved %s articles", saved)
    except Exception as exc:
        logger.error("RSS parse error: %s", exc)


async def send_updates():
    """Send unsent articles to Telegram."""
    if not active_chats:
        logger.warning("send_updates: no active chats — send /start to the bot first")
        return

    try:
        db = get_supabase_client()
        rows = (
            db.table("articles")
            .select("*")
            .eq("is_sent", False)
            .order("created_at")
            .execute()
        )
        if not rows.data:
            logger.info("send_updates: no unsent articles")
            return

        for article in rows.data:
            text = (
                f"<b>{article['title']}</b>\n\n"
                f"{article.get('summary') or ''}\n\n"
                f"Score: {article.get('ai_score', '?')}/10\n"
                f"{article['url']}"
            )
            for chat_id in active_chats:
                try:
                    await bot.send_message(chat_id, text, parse_mode="HTML")
                    logger.info("Sent article to chat %s: %s", chat_id, article["title"])
                except Exception as exc:
                    logger.error("Failed to send to chat %s: %s", chat_id, exc)

            db.table("articles").update({"is_sent": True}).eq(
                "id", article["id"]
            ).execute()
    except Exception as exc:
        logger.error("send_updates error: %s", exc)


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Bot starting...")

    # Start polling in background (drop old updates to avoid stale messages)
    polling_task = asyncio.create_task(
        dp.start_polling(bot, drop_pending_updates=True)
    )
    logger.info("Polling started")

    # Configure scheduler
    scheduler.add_job(scheduled_parse, "interval", hours=2, id="rss_parse")
    scheduler.add_job(send_updates, "interval", minutes=5, id="send_updates")
    scheduler.start()
    logger.info("Scheduler started: RSS every 2h, send_updates every 5min")

    # Run first parse immediately
    asyncio.create_task(scheduled_parse())

    yield

    logger.info("Shutting down...")
    scheduler.shutdown()
    await bot.session.close()
    polling_task.cancel()


app = FastAPI(title="Vibecoding Bot", lifespan=lifespan)


class ArticleRequest(BaseModel):
    title: str
    text: str


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


@app.post("/test-ai")
async def test_ai(article: ArticleRequest):
    result = await analyzer.analyze_text(article.title, article.text)
    return result
