from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    TELEGRAM_TOKEN: str
    SUPABASE_URL: str
    SUPABASE_KEY: str
    DB_PASSWORD: str
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash-lite"


settings = Settings()
