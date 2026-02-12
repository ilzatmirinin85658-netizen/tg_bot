import logging

import feedparser

from app.db.supabase import get_supabase_client
from app.services.ai_service import AIAnalyzer

logger = logging.getLogger(__name__)
analyzer = AIAnalyzer()

MAX_NEW_PER_RUN = 3


async def fetch_and_process_rss(url: str) -> int:
    """Parse RSS feed, analyze new articles with AI, save ALL to DB.

    Returns the number of good articles (score >= 7) found.
    """
    feed = feedparser.parse(url)
    db = get_supabase_client()
    good_count = 0
    analyzed = 0

    for entry in feed.entries:
        if analyzed >= MAX_NEW_PER_RUN:
            logger.info("Hit limit of %d new articles per run, stopping", MAX_NEW_PER_RUN)
            break

        link = entry.get("link", "")
        title = entry.get("title", "")
        if not link or not title:
            continue

        # Check if article already exists in DB
        existing = db.table("articles").select("id").eq("url", link).execute()
        if existing.data:
            continue

        # Analyze with AI
        summary_text = entry.get("summary", "")
        result = await analyzer.analyze_text(title, summary_text)
        score = result.get("score", 0)
        analyzed += 1

        # If AI failed (score=0, no summary) — skip, don't save.
        # The article will be retried on the next run.
        if score == 0 and result.get("summary") is None:
            logger.error("AI failed for url: %s — skipping, will retry later", link)
            continue

        is_good = score >= 7

        # Save to DB — good or bad (but only real AI results, not errors)
        try:
            resp = db.table("articles").insert({
                "url": link,
                "title": title,
                "meaningful_title": result.get("meaningful_title"),
                "summary": result.get("summary"),
                "ai_score": score,
                "is_sent": not is_good,  # bad articles marked as "sent" to skip them
            }).execute()
            logger.info(
                "DB insert OK: title=%s score=%d is_good=%s resp_count=%d",
                title[:60], score, is_good, len(resp.data),
            )
        except Exception as exc:
            logger.error("DB insert FAILED: url=%s error=%s", link, exc)
            continue

        if is_good:
            good_count += 1

    logger.info(
        "RSS done: %s — analyzed=%d, good=%d",
        url, analyzed, good_count,
    )
    return good_count
