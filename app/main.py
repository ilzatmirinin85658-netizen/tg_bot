import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from pydantic import BaseModel

from app.bot.handlers import router
from app.core.config import settings
from app.db.supabase import get_supabase_client
from app.services.ai_service import AIAnalyzer
from app.services.parser import fetch_and_process_rss

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RSS_URL = "https://habr.com/ru/rss/hubs/python/"

bot = Bot(token=settings.TELEGRAM_TOKEN)
dp = Dispatcher()
dp.include_router(router)
analyzer = AIAnalyzer()
scheduler = AsyncIOScheduler()


async def scheduled_parse():
    """Periodic RSS parsing task."""
    try:
        await fetch_and_process_rss(RSS_URL)
    except Exception as exc:
        logger.error("RSS parse error: %s", exc)


async def send_updates():
    """Send unsent articles to Telegram."""
    try:
        db = get_supabase_client()
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
            # Send to the bot's own chat — user should /start the bot first
            # Using bot.send_message to the user who started the bot
            # For now, we broadcast to all chats that messaged the bot
            # by storing chat_id. As a simple start, we log and mark sent.
            try:
                # Try sending to the bot itself won't work;
                # the user needs to /start and we store their chat_id.
                # For MVP: get chat_ids from a simple approach —
                # send to the first user who /start-ed.
                # We'll use getUpdates as a fallback to find chat_id.
                updates = await bot.get_updates(limit=1)
                if updates:
                    chat_id = updates[0].message.chat.id if updates[0].message else None
                else:
                    chat_id = None

                if chat_id:
                    await bot.send_message(chat_id, text, parse_mode="HTML")
                    db.table("articles").update({"is_sent": True}).eq(
                        "id", article["id"]
                    ).execute()
                    logger.info("Sent article: %s", article["title"])
                else:
                    logger.warning("No chat_id found — send /start to the bot first")
                    break
            except Exception as exc:
                logger.error("Failed to send article %s: %s", article["id"], exc)
    except Exception as exc:
        logger.error("send_updates error: %s", exc)


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Start polling in background
    polling_task = asyncio.create_task(dp.start_polling(bot))

    # Configure scheduler
    scheduler.add_job(scheduled_parse, "interval", hours=2, id="rss_parse")
    scheduler.add_job(send_updates, "interval", minutes=5, id="send_updates")
    scheduler.start()
    logger.info("Scheduler started: RSS every 2h, send_updates every 5min")

    # Run first parse immediately
    asyncio.create_task(scheduled_parse())

    yield

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
