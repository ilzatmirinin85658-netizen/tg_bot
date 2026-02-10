import json
import logging

from google import genai

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты эксперт по методологии Vibecoding и AI-разработке. "
    "Оцени статью. Если она полезна для изучения быстрой разработки с ИИ, "
    "дай ей оценку от 1 до 10. Если оценка выше 7, напиши краткую выжимку "
    "(summary) на русском языке (макс 3 предложения). "
    'Верни JSON: {"score": int, "summary": str | null}'
)

MODEL_NAME = "gemini-1.5-flash-latest"


class AIAnalyzer:
    def __init__(self) -> None:
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._models_logged = False

    def _log_available_models(self) -> None:
        if self._models_logged:
            return
        self._models_logged = True
        try:
            models = self.client.models.list()
            names = [m.name for m in models if "flash" in m.name.lower() or "gemini" in m.name.lower()]
            logger.info("Available Gemini models: %s", names)
        except Exception as exc:
            logger.error("Failed to list models: %s", exc)

    async def analyze_text(self, title: str, text: str) -> dict:
        self._log_available_models()

        prompt = f"Заголовок: {title}\n\nТекст: {text}"
        try:
            response = await self.client.aio.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                ),
            )
            raw = response.text.strip()
            # Gemini иногда оборачивает JSON в ```json ... ```
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("Gemini error (model=%s): %s", MODEL_NAME, exc)
            return {"score": 0, "summary": None}
