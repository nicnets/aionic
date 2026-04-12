"""
Helpers for reading system configuration from the database.
Used by collectors, AI provider, and the scheduler in place of .env.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models import SystemConfig


async def get_config(session: AsyncSession, key: str, default: str = "") -> str:
    row = await session.scalar(select(SystemConfig).where(SystemConfig.key == key))
    return row.value if row else default


async def get_config_dict(session: AsyncSession) -> dict[str, str]:
    """Return all config as a plain dict — used to snapshot config for jobs/collectors."""
    rows = await session.scalars(select(SystemConfig))
    return {r.key: r.value for r in rows}


async def set_config(session: AsyncSession, key: str, value: str) -> None:
    row = await session.scalar(select(SystemConfig).where(SystemConfig.key == key))
    if row:
        row.value = value
    else:
        session.add(SystemConfig(key=key, value=value))
    await session.commit()
