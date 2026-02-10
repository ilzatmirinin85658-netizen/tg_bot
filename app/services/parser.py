import logging

import feedparser

from app.db.supabase import get_supabase_client
from app.services.ai_service import AIAnalyzer

logger = logging.getLogger(__name__)
analyzer = AIAnalyzer()


async def fetch_and_process_rss(url: str) -> int:
    """Parse RSS feed, analyze new articles with AI, save good ones to DB.

    Returns the number of articles saved.
    """
    feed = feedparser.parse(url)
    db = get_supabase_client()
    saved = 0

    for entry in feed.entries:
        link = entry.get("link", "")
        title = entry.get("title", "")
        if not link or not title:
            continue

        # Check if article already exists
        existing = db.table("articles").select("id").eq("url", link).execute()
        if existing.data:
            continue

        # Analyze with AI
        summary_text = entry.get("summary", "")
        result = await analyzer.analyze_text(title, summary_text)
        score = result.get("score", 0)

        if score > 7:
            db.table("articles").insert({
                "url": link,
                "title": title,
                "summary": result.get("summary"),
                "ai_score": score,
                "is_sent": False,
            }).execute()
            saved += 1
            logger.info("Saved article: %s (score=%d)", title, score)

    logger.info("RSS processed: %s — saved %d new articles", url, saved)
    return saved
