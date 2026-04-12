"""
RSS/Atom feed collector. Reads active feeds from the rss_feeds DB table.
Falls back to a hardcoded list only if the table is empty (first boot).
Uses feedparser (sync) run in a thread executor.
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
from sqlalchemy import select

from backend.collectors.base import BaseCollector, RawItemData
from backend.db.database import AsyncSessionLocal
from backend.db.models import RssFeed

logger = logging.getLogger(__name__)


def _parse_dt(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return parsedate_to_datetime(val).astimezone(timezone.utc)
            except Exception:
                pass
    return None


def _fetch_feed_sync(url: str) -> list[dict]:
    """Synchronous feedparser call — run via executor."""
    feed = feedparser.parse(url, request_headers={"User-Agent": "aionic/1.0"})
    items = []
    for entry in feed.entries:
        link = getattr(entry, "link", None)
        if not link:
            continue
        source_id = hashlib.md5(link.encode()).hexdigest()
        content = (
            getattr(entry, "summary", None)
            or getattr(entry, "description", None)
            or ""
        )
        items.append(
            RawItemData(
                source_id=source_id,
                url=link,
                title=getattr(entry, "title", None),
                content=content[:4000],
                author=getattr(entry, "author", None),
                published_at=_parse_dt(entry),
                raw_metadata={"feed_url": url, "tags": [t.term for t in getattr(entry, "tags", [])]},
            )
        )
    return items


class RSSCollector(BaseCollector):
    source_name = "rss"

    async def _load_feeds(self) -> list[RssFeed]:
        """Load active feeds from DB."""
        async with AsyncSessionLocal() as session:
            rows = await session.scalars(
                select(RssFeed).where(RssFeed.is_active == True).order_by(RssFeed.id)
            )
            return list(rows)

    async def _update_feed_stats(
        self,
        feed_id: int,
        *,
        success: bool,
        item_count: int = 0,
        error_msg: str | None = None,
    ) -> None:
        async with AsyncSessionLocal() as session:
            feed = await session.get(RssFeed, feed_id)
            if not feed:
                return
            feed.last_collected_at = datetime.now(timezone.utc)
            if success:
                feed.last_error = None
                feed.item_count = (feed.item_count or 0) + item_count
            else:
                feed.error_count = (feed.error_count or 0) + 1
                feed.last_error = error_msg or "Unknown error"
            await session.commit()

    async def fetch_items(self) -> list[RawItemData]:
        feeds = await self._load_feeds()
        if not feeds:
            logger.warning("No active RSS feeds in DB — skipping RSS collection")
            return []

        loop = asyncio.get_event_loop()

        # Fetch all feeds concurrently
        tasks = [
            loop.run_in_executor(None, _fetch_feed_sync, feed.url)
            for feed in feeds
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items: list[RawItemData] = []
        for feed, result in zip(feeds, results):
            if isinstance(result, Exception):
                logger.warning("RSS feed failed %s (%s): %s", feed.name, feed.url, result)
                asyncio.create_task(
                    self._update_feed_stats(feed.id, success=False, error_msg=str(result))
                )
            else:
                all_items.extend(result)
                asyncio.create_task(
                    self._update_feed_stats(feed.id, success=True, item_count=len(result))
                )

        return all_items
