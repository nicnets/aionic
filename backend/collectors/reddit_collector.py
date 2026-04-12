"""
Reddit collector. Uses PRAW (via asyncpraw) for authenticated access,
falls back to the public JSON API if credentials are missing.
"""
import logging
from datetime import datetime, timezone

import httpx

from backend.collectors.base import BaseCollector, RawItemData

logger = logging.getLogger(__name__)

SUBREDDITS = [
    "MachineLearning",
    "artificial",
    "LocalLLaMA",
    "ChatGPT",
    "singularity",
    "deeplearning",
    "OpenAI",
    "StableDiffusion",
    "LanguageModelEval",
    "learnmachinelearning",
]
POSTS_PER_SUB = 25


class RedditCollector(BaseCollector):
    source_name = "reddit"

    async def _fetch_via_praw(self) -> list[RawItemData]:
        import asyncpraw
        reddit = asyncpraw.Reddit(
            client_id=self._cfg("reddit_client_id"),
            client_secret=self._cfg("reddit_client_secret"),
            user_agent=self._cfg("reddit_user_agent", "aionic/1.0"),
        )
        items: list[RawItemData] = []
        try:
            for sub_name in SUBREDDITS:
                try:
                    sub = await reddit.subreddit(sub_name)
                    async for post in sub.hot(limit=POSTS_PER_SUB):
                        items.append(self._post_to_item(sub_name, post.id, post))
                except Exception:
                    logger.exception("Reddit PRAW failed for r/%s", sub_name)
        finally:
            await reddit.close()
        return items

    def _post_to_item(self, sub_name: str, post_id: str, post) -> RawItemData:
        published_at = None
        ts = getattr(post, "created_utc", None)
        if ts:
            published_at = datetime.fromtimestamp(ts, tz=timezone.utc)
        return RawItemData(
            source_id=post_id,
            url=f"https://reddit.com{getattr(post, 'permalink', '')}",
            title=getattr(post, "title", None),
            content=(getattr(post, "selftext", "") or "")[:4000],
            author=str(getattr(post, "author", "") or ""),
            published_at=published_at,
            raw_metadata={
                "subreddit": sub_name,
                "score": getattr(post, "score", 0),
                "num_comments": getattr(post, "num_comments", 0),
                "url": getattr(post, "url", None),
                "is_self": getattr(post, "is_self", False),
            },
        )

    async def _fetch_via_json_api(self) -> list[RawItemData]:
        """Public JSON API fallback — no auth needed, limited to top posts."""
        headers = {"User-Agent": "aionic/1.0 (content intelligence)"}
        items: list[RawItemData] = []
        async with httpx.AsyncClient(headers=headers, timeout=20) as client:
            for sub_name in SUBREDDITS:
                try:
                    resp = await client.get(
                        f"https://www.reddit.com/r/{sub_name}/hot.json",
                        params={"limit": POSTS_PER_SUB},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception:
                    logger.exception("Reddit JSON API failed for r/%s", sub_name)
                    continue

                for child in data.get("data", {}).get("children", []):
                    p = child.get("data", {})
                    post_id = p.get("id", "")
                    if not post_id:
                        continue
                    ts = p.get("created_utc")
                    published_at = (
                        datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
                    )
                    items.append(
                        RawItemData(
                            source_id=post_id,
                            url=f"https://reddit.com{p.get('permalink', '')}",
                            title=p.get("title"),
                            content=(p.get("selftext") or "")[:4000],
                            author=p.get("author"),
                            published_at=published_at,
                            raw_metadata={
                                "subreddit": sub_name,
                                "score": p.get("score", 0),
                                "num_comments": p.get("num_comments", 0),
                                "url": p.get("url"),
                                "is_self": p.get("is_self", False),
                            },
                        )
                    )
        return items

    async def fetch_items(self) -> list[RawItemData]:
        if self._cfg("reddit_client_id") and self._cfg("reddit_client_secret"):
            try:
                return await self._fetch_via_praw()
            except ImportError:
                logger.warning("asyncpraw not installed, falling back to JSON API")
        return await self._fetch_via_json_api()
