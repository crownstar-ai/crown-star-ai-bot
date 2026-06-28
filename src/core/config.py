from pydantic_settings import BaseSettings
from pydantic import validator
import os
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "CrownStar"
    APP_VERSION: str = "7.0.1"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/crownstar.db"
    REDIS_URL: Optional[str] = None
    SECRET_KEY: str = "change_me_in_production"
    LICENSE_SECRET: str = "change_me_in_production"
    CROWNSTAR_LICENSE_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEFAULT_TEMPERATURE: float = 0.7
    DEFAULT_MIN_LENGTH: int = 10
    DEFAULT_MAX_LENGTH: int = 2048
    MEMORY_WINDOW: int = 5
    LOG_LEVEL: str = "INFO"
    DEFAULT_TENANT: Optional[str] = None

    @validator("SECRET_KEY")
    def check_secret_key(cls, v):
        if v == "change_me_in_production" and os.environ.get("ENVIRONMENT") == "production":
            raise ValueError("SECRET_KEY must be changed in production!")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

def get_settings():
    return Settings()
