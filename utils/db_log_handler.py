# -*- coding: utf-8 -*-
"""
utils/db_log_handler.py
Async-safe logging handler that writes to app_logs without touching the API's
main async engine or event loop.
"""
import asyncio
import logging
import queue
import threading
import traceback
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import settings


class DBLogHandler(logging.Handler):
    """
    Logging handler that writes records to the AppLog table.

    Important: this handler owns its own event loop and async SQLAlchemy engine
    inside a dedicated background thread. That keeps asyncpg connections bound to
    a single loop and avoids poisoning the API request pool.
    """

    def __init__(self, min_level: int = logging.WARNING):
        super().__init__(min_level)
        self._queue: queue.Queue = queue.Queue(maxsize=5000)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._worker,
            daemon=True,
            name="db-log-handler",
        )
        self._thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            exc_text = None
            if record.exc_info:
                exc_text = "".join(traceback.format_exception(*record.exc_info))
            self._queue.put_nowait({
                "timestamp": datetime.now(timezone.utc),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "exception": exc_text,
                "source": f"{record.pathname}:{record.lineno}",
            })
        except queue.Full:
            pass

    def _worker(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        engine = None
        session_factory = None

        try:
            engine = create_async_engine(
                settings.DATABASE_URL,
                pool_size=2,
                max_overflow=0,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
            )
            session_factory = async_sessionmaker(
                engine,
                expire_on_commit=False,
                autoflush=False,
            )

            while not self._stop_event.is_set() or not self._queue.empty():
                try:
                    entry = self._queue.get(timeout=2)
                except queue.Empty:
                    continue

                try:
                    loop.run_until_complete(self._async_insert(session_factory, entry))
                except Exception:
                    pass
                finally:
                    self._queue.task_done()
        finally:
            if engine is not None:
                try:
                    loop.run_until_complete(engine.dispose())
                except Exception:
                    pass
            loop.close()

    @staticmethod
    async def _async_insert(session_factory: async_sessionmaker, entry: dict) -> None:
        from db.models import AppLog

        async with session_factory() as db:
            try:
                db.add(AppLog(**entry))
                await db.commit()
            except Exception:
                await db.rollback()

    def close(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=5)
        super().close()


_db_handler: DBLogHandler | None = None


def install_db_handler(min_level: int = logging.WARNING) -> DBLogHandler:
    global _db_handler
    if _db_handler is not None:
        return _db_handler
    _db_handler = DBLogHandler(min_level=min_level)
    logging.getLogger().addHandler(_db_handler)
    return _db_handler
