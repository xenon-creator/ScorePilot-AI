import os
from typing import List, Optional
from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "AegisGrading AI"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 Days

    # Database Settings
    POSTGRES_SERVER: str = os.getenv("DB_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("DB_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("DB_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("DB_NAME", "aegis_grading")

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis/Celery Settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # MinIO / Object Storage Settings
    S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", "localhost:9000")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "minioadmin")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "minioadmin")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "exam-papers")

    # Sentence Transformers Caching
    SENTENCE_TRANSFORMERS_HOME: str = os.getenv("SENTENCE_TRANSFORMERS_HOME", "./models")

    # AI Scoring Constants
    AI_CONFIDENCE_THRESHOLD: float = 0.85  # Flag if below this threshold

    # OCR Configurations
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", None)
    TESSERACT_CMD_PATH: str = os.getenv("TESSERACT_CMD_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    TESSERACT_LANGS: str = os.getenv("TESSERACT_LANGS", "eng")
    LMS_URL: Optional[str] = os.getenv("LMS_URL", None)
    LMS_TOKEN: Optional[str] = os.getenv("LMS_TOKEN", None)

    # SMTP / Email Settings
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "ScorePilot AI <noreply@scorepilot.ai>")
    STUDENT_PORTAL_URL: str = os.getenv("STUDENT_PORTAL_URL", "http://localhost:3000")

    model_config = ConfigDict(case_sensitive=True)

settings = Settings()
