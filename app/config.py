"""
KTS API — Configuration
Loads settings from environment variables with sensible defaults.
"""
from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/kts_db"

    # JWT
    JWT_SECRET_KEY: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 10080  # 7 days

    # Firebase
    FIREBASE_CREDENTIALS_PATH: str = "./firebase-credentials.json"

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

    # App
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    CORS_ORIGINS: str = '["http://localhost:3000","http://localhost:8081"]'

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.CORS_ORIGINS)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
