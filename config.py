"""
OTT Monitor - Application Configuration
Reads from environment variables with sensible defaults.
"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Application ─────────────────────────────────────────────────────────
    ENV: str = "development"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://ott_user:password@localhost:5432/ott_monitor"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # ── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_TTL_DEFAULT: int = 60           # seconds
    REDIS_TTL_SUMMARY: int = 30           # dashboard summary cache
    REDIS_TTL_CHANNEL: int = 10           # per-channel status cache

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:80"]

    # ── Workers ──────────────────────────────────────────────────────────────
    MONITOR_INTERVAL: int = 300           # seconds between checks
    STREAMS_PER_WORKER: int = 20
    WORKER_TIMEOUT: int = 30              # ffprobe timeout per stream
    WORKER_RETRY_ATTEMPTS: int = 3
    WORKER_RETRY_DELAY: int = 5

    # ── Simulation ───────────────────────────────────────────────────────────
    SIMULATE_MODE: bool = True            # use simulated data (no real streams)

    # ── Alerting ─────────────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    ALERT_FROM: str = "noc@company.com"
    ALERT_TO: str = "oncall@company.com"
    WEBHOOK_URL: str = ""

    # ── Thresholds ───────────────────────────────────────────────────────────
    BITRATE_DROP_THRESHOLD: float = 0.5   # 50% drop triggers alert
    AUDIO_SILENCE_THRESHOLD: int = 60     # seconds
    VIDEO_JITTER_THRESHOLD: float = 50.0  # ms
    RESPONSE_TIME_THRESHOLD: int = 5000   # ms — stream considered slow

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
