import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from pydantic import BaseModel

import app.bot.handlers as handlers
from app.bot.handlers import router
from app.bot.scheduler import publish_one
from app.core.config import settings
from app.services.ai_service import AIAnalyzer
from app.services.parser import fetch_and_process_rss  # noqa: used in scheduled_parse

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
    if not handlers.bot_active:
        logger.info("[Scheduler] Bot is sleeping, skipping parse")
        return

    logger.info("[Hunter] \U0001f552 Запуск парсинга новостей...")
    try:
        saved = await fetch_and_process_rss(RSS_URL)
        logger.info("[Hunter] Парсинг завершен: найдено %s новых статей. Следующий запуск через 1 час.", saved)
    except Exception as exc:
        logger.error("[Hunter] RSS parse error: %s", exc)
        try:
            await bot.send_message(
                settings.ADMIN_ID,
                f"\u26a0\ufe0f [Hunter] \u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u0430\u0440\u0441\u0438\u043d\u0433\u0430: {exc}",
            )
        except Exception:
            pass


async def send_updates():
    """Publisher: send ONE unsent article to all users."""
    if not handlers.bot_active:
        logger.info("[Publisher] Bot is sleeping, skipping send")
        return

    logger.info("[Publisher] \U0001f4e4 \u041f\u0440\u043e\u0432\u0435\u0440\u044f\u044e \u043e\u0447\u0435\u0440\u0435\u0434\u044c \u043f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u0439...")
    try:
        published = await publish_one(bot)
        if published:
            logger.info("[Publisher] \u0413\u043e\u0442\u043e\u0432\u043e. \u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0430\u044f \u043f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u044f \u0447\u0435\u0440\u0435\u0437 4 \u0447\u0430\u0441\u0430.")
    except Exception as exc:
        logger.error("[Publisher] error: %s", exc)
        try:
            await bot.send_message(
                settings.ADMIN_ID,
                f"\u26a0\ufe0f [Publisher] \u041e\u0448\u0438\u0431\u043a\u0430: {exc}",
            )
        except Exception:
            pass


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Bot starting...")

    # Start polling in background (drop old updates to avoid stale messages)
    polling_task = asyncio.create_task(
        dp.start_polling(bot, drop_pending_updates=True)
    )
    logger.info("Polling started")

    # Configure scheduler
    scheduler.add_job(scheduled_parse, "interval", hours=1, id="rss_parse")
    scheduler.add_job(send_updates, "interval", hours=4, id="send_updates")
    scheduler.start()
    logger.info("Scheduler started: Hunter every 1h, Publisher every 4h")

    for job in scheduler.get_jobs():
        logger.info("[Scheduler] Job: %s | next run: %s", job.id, job.next_run_time)

    # At startup: immediately check if there are queued articles to publish
    async def startup_tasks():
        logger.info("[Startup] Проверяю очередь на неотправленные статьи...")
        await send_updates()
        # Then delayed first parse (1 min) so the system has time to warm up
        logger.info("[Startup] Первый парсинг запланирован через 1 минуту...")
        await asyncio.sleep(60)
        await scheduled_parse()

    asyncio.create_task(startup_tasks())

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
