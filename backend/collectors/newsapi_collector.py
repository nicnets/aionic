"""
NewsAPI collector. Fetches AI/ML news articles.
Requires NEWSAPI_KEY.
"""
import hashlib
import logging
from datetime import datetime, timedelta, timezone

import httpx

from backend.collectors.base import BaseCollector, RawItemData

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/everything"
QUERIES = [
    "artificial intelligence OR large language model",
    "ChatGPT OR Claude OR Gemini",
    "machine learning research",
    "AI startup funding",
]
PAGE_SIZE = 30


class NewsAPICollector(BaseCollector):
    source_name = "newsapi"

    async def fetch_items(self) -> list[RawItemData]:
        newsapi_key = self._cfg("newsapi_key")
        if not newsapi_key:
            logger.info("NewsAPI key not configured, skipping")
            return []

        from_dt = (datetime.now(timezone.utc) - timedelta(days=3)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        seen: set[str] = set()
        items: list[RawItemData] = []

        async with httpx.AsyncClient(timeout=20) as client:
            for query in QUERIES:
                try:
                    resp = await client.get(
                        NEWSAPI_URL,
                        params={
                            "q": query,
                            "from": from_dt,
                            "sortBy": "publishedAt",
                            "pageSize": PAGE_SIZE,
                            "language": "en",
                            "apiKey": newsapi_key,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception:
                    logger.exception("NewsAPI query failed: %s", query)
                    continue

                for article in data.get("articles", []):
                    url = article.get("url", "")
                    if not url or url == "[Removed]":
                        continue
                    source_id = hashlib.md5(url.encode()).hexdigest()
                    if source_id in seen:
                        continue
                    seen.add(source_id)

                    published_str = article.get("publishedAt")
                    published_at = None
                    if published_str:
                        try:
                            published_at = datetime.fromisoformat(
                                published_str.replace("Z", "+00:00")
                            )
                        except ValueError:
                            pass

                    content = " ".join(
                        filter(None, [article.get("description"), article.get("content")])
                    )
                    items.append(
                        RawItemData(
                            source_id=source_id,
                            url=url,
                            title=article.get("title"),
                            content=content[:4000],
                            author=article.get("author"),
                            published_at=published_at,
                            raw_metadata={
                                "source_name": article.get("source", {}).get("name"),
                                "query": query,
                            },
                        )
                    )

        return items
