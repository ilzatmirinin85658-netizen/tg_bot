from fastapi import FastAPI
from pydantic import BaseModel

from app.services.ai_service import AIAnalyzer

app = FastAPI(title="Vibecoding Bot")
analyzer = AIAnalyzer()


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
