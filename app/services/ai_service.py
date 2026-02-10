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

FALLBACK_MODEL = "models/gemini-2.0-flash"


class AIAnalyzer:
    def __init__(self) -> None:
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._models_logged = False
        logger.info(
            "AIAnalyzer initialized: primary=%s, fallback=%s",
            settings.GEMINI_MODEL, FALLBACK_MODEL,
        )

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

    async def _generate(self, model: str, prompt: str) -> str:
        response = await self.client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
        )
        return response.text.strip()

    async def analyze_text(self, title: str, text: str) -> dict:
        self._log_available_models()

        primary = settings.GEMINI_MODEL
        prompt = f"Заголовок: {title}\n\nТекст: {text}"

        # Try primary model
        try:
            raw = await self._generate(primary, prompt)
        except Exception as exc:
            if "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc):
                logger.warning(
                    "Лимиты %s исчерпаны, переключаюсь на резерв (%s)...",
                    primary, FALLBACK_MODEL,
                )
                # Try fallback model
                try:
                    raw = await self._generate(FALLBACK_MODEL, prompt)
                except Exception as fallback_exc:
                    logger.error(
                        "Fallback model %s also failed: %s", FALLBACK_MODEL, fallback_exc,
                    )
                    return {"score": 0, "summary": None}
            else:
                logger.error("Gemini error (model=%s): %s", primary, exc)
                return {"score": 0, "summary": None}

        # Parse JSON response
        try:
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("Gemini JSON parse error: %s | raw=%s", exc, raw[:200])
            return {"score": 0, "summary": None}
