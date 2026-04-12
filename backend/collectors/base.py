"""
Abstract base class for all data collectors.
Each collector is responsible for fetching items from one source and
upserting them into raw_items. Deduplication at this stage is by
source + source_id. Content-level MinHash dedup happens in the processor.
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import AsyncSessionLocal
from backend.db.models import RawItem

logger = logging.getLogger(__name__)


class RawItemData(TypedDict, total=False):
    source_id: str           # required — unique ID within this source
    url: str | None
    title: str | None
    content: str | None
    author: str | None
    published_at: datetime | None
    raw_metadata: dict | None


class BaseCollector(ABC):
    """
    Subclass must set `source_name` and implement `fetch_items()`.
    Call `collect()` to run the full fetch + save cycle.

    Pass `config` (from get_config_dict) so collectors can read API keys
    without touching .env or re-querying the DB on every call.
    """

    source_name: str = ""

    def __init__(self, config: dict[str, str] | None = None):
        self._config = config or {}

    def _cfg(self, key: str, default: str = "") -> str:
        """Read a value from the injected config dict."""
        return self._config.get(key, default)

    @abstractmethod
    async def fetch_items(self) -> list[RawItemData]:
        """Return a list of raw item dicts from the source."""
        ...

    async def collect(self) -> int:
        """
        Fetch items and save new ones to the DB.
        Returns count of newly inserted items.
        """
        try:
            items = await self.fetch_items()
        except Exception:
            logger.exception("Collector %s: fetch_items failed", self.source_name)
            return 0

        if not items:
            return 0

        new_count = 0
        async with AsyncSessionLocal() as session:
            for item in items:
                try:
                    is_new = await self._upsert(item, session)
                    if is_new:
                        new_count += 1
                except Exception:
                    logger.exception(
                        "Collector %s: failed to save item %s",
                        self.source_name,
                        item.get("source_id", "?"),
                    )

        logger.info("Collector %s: %d new / %d total", self.source_name, new_count, len(items))
        return new_count

    async def _upsert(self, data: RawItemData, session: AsyncSession) -> bool:
        """
        Insert if source+source_id not already present.
        Returns True if a new row was inserted.
        """
        existing = await session.scalar(
            select(RawItem).where(
                RawItem.source == self.source_name,
                RawItem.source_id == data["source_id"],
            )
        )
        if existing:
            return False

        item = RawItem(
            source=self.source_name,
            source_id=data["source_id"],
            url=data.get("url"),
            title=data.get("title"),
            content=data.get("content"),
            author=data.get("author"),
            published_at=data.get("published_at"),
            raw_metadata=data.get("raw_metadata"),
            collected_at=datetime.now(timezone.utc),
        )
        session.add(item)
        await session.commit()
        return True
