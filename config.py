# -*- coding: utf-8 -*-
"""OTT Monitor - Application Configuration"""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV:           str  = "development"
    API_PORT:      int  = 8000
    API_WORKERS:   int  = 4
    LOG_LEVEL:     str  = "INFO"
    LOG_FORMAT:    str  = "json"

    DATABASE_URL:    str = "postgresql+asyncpg://ott_user:password@localhost:5432/ott_monitor"
    DB_POOL_SIZE:    int = 8
    DB_MAX_OVERFLOW: int = 4
    DB_ECHO:         bool = False

    REDIS_URL:          str = "redis://localhost:6379"
    REDIS_TTL_DEFAULT:  int = 60
    REDIS_TTL_SUMMARY:  int = 30
    REDIS_TTL_CHANNEL:  int = 10

    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:80"]

    MONITOR_INTERVAL:      int = 300
    STREAMS_PER_WORKER:    int = 5
    WORKER_TIMEOUT:        int = 30
    WORKER_RETRY_ATTEMPTS: int = 3
    WORKER_RETRY_DELAY:    int = 5
    ALERT_DISPATCH_CONCURRENCY: int = 2
    ALERT_CONFIG_CACHE_TTL:     int = 30
    WORKER_STATUS_TTL:          int = 900

    SIMULATE_MODE: bool = True

    SMTP_HOST:   str = "smtp.gmail.com"
    SMTP_PORT:   int = 587
    SMTP_USER:   str = ""
    SMTP_PASS:   str = ""
    ALERT_FROM:  str = "noc@company.com"
    ALERT_TO:    str = "oncall@company.com"
    WEBHOOK_URL: str = ""

    BITRATE_DROP_THRESHOLD:  float = 0.5
    AUDIO_SILENCE_THRESHOLD: int   = 60
    VIDEO_JITTER_THRESHOLD:  float = 50.0
    RESPONSE_TIME_THRESHOLD: int   = 5000

    JWT_SECRET_KEY:              str = "CHANGE_THIS_IN_PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REFRESH_TOKEN_EXPIRE_DAYS:   int = 7
    SCHEDULER_API_TOKEN:         str = ""
    INTERNAL_API_URL:            str = "http://api:8000"

    TOTAL_WORKERS: int = 15

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
