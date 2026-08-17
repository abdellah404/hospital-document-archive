from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):

    database_url: str

    jwt_secret: str

    jwt_algorithm: str = "HS256"

    access_token_expire_minutes: int = 30

    gemini_api_key: str

    gemini_model: str = "gemini-3.6-flash"

    redis_url: str = "redis://localhost:6379/0"

    seed_admin_username: str = "admin"
    seed_admin_email: str = "admin@gmail.com"
    seed_admin_password: str = "admin"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()