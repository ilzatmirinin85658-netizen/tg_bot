from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    TELEGRAM_TOKEN: str
    SUPABASE_URL: str
    SUPABASE_KEY: str
    DB_PASSWORD: str
    GEMINI_API_KEY: str


settings = Settings()
