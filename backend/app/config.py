from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    JWT_SECRET: str
    SESSION_COOKIE_NAME: str = "focus_session"

    APP_BASE_URL: str = "https://focus.baltito.com"

    DATABASE_URL: str = "sqlite:////data/focus.db"

    # --- LLM + Voice (OpenAI-compatible: Groq default) ---
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_API_KEY: str | None = None
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    WHISPER_MODEL: str = "whisper-large-v3-turbo"
    LLM_TIMEOUT: int = 60


settings = Settings()


class AIProviderUnavailable(RuntimeError):
    """Raised when optional AI provider configuration is missing."""


def require_ai_provider_configured() -> None:
    if not settings.LLM_API_KEY:
        raise AIProviderUnavailable("LLM_API_KEY is not configured")
