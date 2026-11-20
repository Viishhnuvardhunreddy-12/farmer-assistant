from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # Phase 0 decisions
    crop: str = "paddy"
    region: str = ""
    language_code: str = "te"
    language_name: str = "Telugu"
    expert_contact: str = "Kisan Call Centre: 1800-180-1551 (toll free)"

    # LLM: "gemini" or "claude"
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-5-5"

    # RAG
    sources_dir: Path = ROOT / "data" / "sources"
    chroma_dir: Path = ROOT / "data" / "processed" / "chroma"
    min_source_similarity: float = 0.35
    retrieval_top_k: int = 6

    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""

    # WhatsApp Cloud API
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_api_version: str = "v23.0"

    # Speech
    speech_provider: str = "none"

    # Storage / privacy
    db_path: Path = ROOT / "data" / "app.db"
    user_id_salt: str = "change-me"

    @property
    def collection_name(self) -> str:
        return f"sources_{self.crop.lower().replace(' ', '_')}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
