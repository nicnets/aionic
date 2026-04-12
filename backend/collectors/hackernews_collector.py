"""
Hacker News collector via Algolia Search API.
Fetches top AI/ML stories from the last 24 hours.
"""
import logging
from datetime import datetime, timedelta, timezone

import httpx

from backend.collectors.base import BaseCollector, RawItemData

logger = logging.getLogger(__name__)

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"
QUERIES = ["llm", "large language model", "machine learning", "artificial intelligence", "gpt", "claude ai"]
MAX_PER_QUERY = 30


class HackerNewsCollector(BaseCollector):
    source_name = "hn"

    async def fetch_items(self) -> list[RawItemData]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=3)
        cutoff_ts = int(cutoff.timestamp())

        seen_ids: set[str] = set()
        items: list[RawItemData] = []

        async with httpx.AsyncClient(timeout=20) as client:
            for query in QUERIES:
                try:
                    resp = await client.get(
                        ALGOLIA_URL,
                        params={
                            "query": query,
                            "tags": "story",
                            "hitsPerPage": MAX_PER_QUERY,
                            "numericFilters": f"created_at_i>{cutoff_ts}",
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception:
                    logger.exception("HN query failed: %s", query)
                    continue

                for hit in data.get("hits", []):
                    story_id = str(hit.get("objectID", ""))
                    if not story_id or story_id in seen_ids:
                        continue
                    seen_ids.add(story_id)

                    url = hit.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
                    ts = hit.get("created_at_i")
                    published_at = (
                        datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
                    )

                    items.append(
                        RawItemData(
                            source_id=story_id,
                            url=url,
                            title=hit.get("title"),
                            content=hit.get("story_text") or "",
                            author=hit.get("author"),
                            published_at=published_at,
                            raw_metadata={
                                "points": hit.get("points", 0),
                                "num_comments": hit.get("num_comments", 0),
                                "hn_url": f"https://news.ycombinator.com/item?id={story_id}",
                            },
                        )
                    )

        return items
