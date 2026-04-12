"""
Stack Overflow collector. Fetches active questions on AI/ML tags
via the Stack Exchange API (no auth required for read-only).
"""
import logging
from datetime import datetime, timedelta, timezone

import httpx

from backend.collectors.base import BaseCollector, RawItemData

logger = logging.getLogger(__name__)

SE_API = "https://api.stackexchange.com/2.3/questions"
TAGS = [
    "machine-learning",
    "deep-learning",
    "large-language-model",
    "pytorch",
    "transformers",
    "langchain",
    "huggingface",
    "openai-api",
]
PAGE_SIZE = 30


class StackOverflowCollector(BaseCollector):
    source_name = "stackoverflow"

    async def fetch_items(self) -> list[RawItemData]:
        from_ts = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
        seen: set[str] = set()
        items: list[RawItemData] = []

        async with httpx.AsyncClient(timeout=20) as client:
            for tag in TAGS:
                try:
                    resp = await client.get(
                        SE_API,
                        params={
                            "order": "desc",
                            "sort": "activity",
                            "tagged": tag,
                            "site": "stackoverflow",
                            "pagesize": PAGE_SIZE,
                            "fromdate": from_ts,
                            "filter": "!nNPvSNdWme",  # include body_markdown
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception:
                    logger.exception("Stack Overflow query failed for tag: %s", tag)
                    continue

                for q in data.get("items", []):
                    q_id = str(q.get("question_id", ""))
                    if not q_id or q_id in seen:
                        continue
                    seen.add(q_id)

                    creation_date = q.get("creation_date")
                    published_at = (
                        datetime.fromtimestamp(creation_date, tz=timezone.utc)
                        if creation_date
                        else None
                    )

                    items.append(
                        RawItemData(
                            source_id=q_id,
                            url=q.get("link"),
                            title=q.get("title"),
                            content=(q.get("body_markdown") or "")[:4000],
                            author=q.get("owner", {}).get("display_name"),
                            published_at=published_at,
                            raw_metadata={
                                "tags": q.get("tags", []),
                                "score": q.get("score", 0),
                                "answer_count": q.get("answer_count", 0),
                                "view_count": q.get("view_count", 0),
                                "is_answered": q.get("is_answered", False),
                                "search_tag": tag,
                            },
                        )
                    )

        return items
