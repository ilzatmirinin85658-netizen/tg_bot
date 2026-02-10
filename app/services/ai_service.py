import json
import logging

import google.generativeai as genai

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты эксперт по методологии Vibecoding и AI-разработке. "
    "Оцени статью. Если она полезна для изучения быстрой разработки с ИИ, "
    "дай ей оценку от 1 до 10. Если оценка выше 7, напиши краткую выжимку "
    "(summary) на русском языке (макс 3 предложения). "
    'Верни JSON: {"score": int, "summary": str | null}'
)


class AIAnalyzer:
    def __init__(self) -> None:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            "gemini-2.0-flash",
            system_instruction=SYSTEM_PROMPT,
        )

    async def analyze_text(self, title: str, text: str) -> dict:
        prompt = f"Заголовок: {title}\n\nТекст: {text}"
        try:
            response = await self.model.generate_content_async(prompt)
            raw = response.text.strip()
            # Gemini иногда оборачивает JSON в ```json ... ```
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("Gemini error: %s", exc)
            return {"score": 0, "summary": None}
