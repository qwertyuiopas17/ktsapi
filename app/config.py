"""
KTS API — Configuration
Loads settings from environment variables with sensible defaults.
"""
import json
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_JWT_SECRET = "change-this-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "sqlite:///./kts_dev.db"
    DB_ECHO: bool = False

    # JWT
    JWT_SECRET_KEY: str = _INSECURE_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60  # short-lived access token
    REFRESH_TOKEN_EXPIRY_DAYS: int = 30

    # Firebase Phone Auth
    FIREBASE_CREDENTIALS_PATH: str = "./firebase-credentials.json"
    FIREBASE_PROJECT_ID: str = ""
    # Accepts "dev:<phone>" in place of a Firebase ID token. Never enabled in production.
    AUTH_DEV_STUB: bool = False

    # PIN unlock
    PIN_MAX_ATTEMPTS: int = 5

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = "kts-bill-images"
    AWS_S3_REGION: str = "ap-south-1"

    # Google Document AI
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GOOGLE_PROJECT_ID: str = ""
    GOOGLE_LOCATION: str = "us"
    GOOGLE_PROCESSOR_ID: str = ""

    # Rate limiting (slowapi). Use redis://... in multi-worker deployments.
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_STORAGE_URI: str = "memory://"
    RATE_LIMIT_DEFAULT: str = "300/minute"
    RATE_LIMIT_AUTH: str = "20/minute"

    # Observability
    SENTRY_DSN: str = ""
    LOG_JSON: bool = True
    LOG_LEVEL: str = "INFO"

    # App
    APP_ENV: str = "development"  # development | test | staging | production
    APP_DEBUG: bool = False
    CORS_ORIGINS: str = '["http://localhost:3000","http://localhost:8081"]'

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.CORS_ORIGINS)

    @property
    def is_production_like(self) -> bool:
        return self.APP_ENV in ("staging", "production")

    @model_validator(mode="after")
    def _check_production_safety(self):
        if self.is_production_like:
            if self.JWT_SECRET_KEY == _INSECURE_JWT_SECRET or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("JWT_SECRET_KEY must be set to a random value of 32+ chars outside development")
            if self.AUTH_DEV_STUB:
                raise ValueError("AUTH_DEV_STUB must be disabled in staging/production")
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("SQLite is not supported in staging/production")
        return self


settings = Settings()
