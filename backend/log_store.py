"""
In-memory log store. Captures all Python log records emitted anywhere in the
backend and makes them available via the admin API.

Wire up once at startup by calling install().
"""
import logging
from collections import deque
from datetime import datetime, timezone
from typing import TypedDict


class LogRecord(TypedDict):
    t: str        # HH:MM:SS UTC
    level: str    # DEBUG | INFO | WARNING | ERROR | CRITICAL
    logger: str   # logger name (e.g. "backend.processors.pipeline")
    msg: str      # formatted message


_store: deque[LogRecord] = deque(maxlen=1000)


class _MemoryHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            _store.append(LogRecord(
                t=datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S"),
                level=record.levelname,
                logger=record.name,
                msg=self.format(record),
            ))
        except Exception:
            pass  # never crash the app because of logging


_handler = _MemoryHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))


def install() -> None:
    """Attach the memory handler to the root logger. Call once at startup."""
    root = logging.getLogger()
    if _handler not in root.handlers:
        root.addHandler(_handler)
    # Ensure uvicorn loggers propagate so we capture their output too
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        lg = logging.getLogger(name)
        lg.propagate = True


def get_logs(level: str | None = None, limit: int = 500) -> list[LogRecord]:
    """Return recent log records, optionally filtered by level."""
    records = list(_store)
    if level:
        level_up = level.upper()
        records = [r for r in records if r["level"] == level_up]
    return records[-limit:]


def clear() -> None:
    _store.clear()
