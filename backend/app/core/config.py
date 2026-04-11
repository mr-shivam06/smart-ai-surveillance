"""
=============================================================
  File : backend/app/core/config.py
  Purpose : App-wide settings loaded from .env
=============================================================
"""

from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    # JWT
    SECRET_KEY      : str  = "CHANGE_ME_IN_PRODUCTION_USE_LONG_RANDOM_STRING"
    ALGORITHM       : str  = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24   # 24 hours

    # Database
    DATABASE_URL: str = "sqlite:///./surveillance.db"

    # AI
    MODEL_PATH      : str  = "backend/yolov8n.pt"
    CONFIDENCE      : float = 0.50

    # Paths
    FACE_DB_DIR     : str  = "backend/face_db"
    SCREENSHOTS_DIR : str  = "backend/screenshots"
    SNAPSHOTS_DIR   : str  = "backend/snapshots"
    LOGS_DIR        : str  = "backend/logs"
    ZONES_CONFIG    : str  = "backend/zones.json"

    class Config:
        env_file = "backend/.env"
        extra    = "ignore"


settings = Settings()