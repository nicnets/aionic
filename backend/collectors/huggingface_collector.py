"""
Hugging Face collector. Fetches trending models, datasets, and spaces
from the HuggingFace Hub API.
"""
import logging
from datetime import datetime, timezone

import httpx

from backend.collectors.base import BaseCollector, RawItemData

logger = logging.getLogger(__name__)

HF_API = "https://huggingface.co/api"
MAX_MODELS = 50
MAX_SPACES = 30


class HuggingFaceCollector(BaseCollector):
    source_name = "huggingface"

    async def fetch_items(self) -> list[RawItemData]:
        headers = {}
        if token := self._cfg("huggingface_token"):
            headers["Authorization"] = f"Bearer {token}"

        items: list[RawItemData] = []
        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            items.extend(await self._fetch_models(client))
            items.extend(await self._fetch_spaces(client))
        return items

    async def _fetch_models(self, client: httpx.AsyncClient) -> list[RawItemData]:
        try:
            resp = await client.get(
                f"{HF_API}/models",
                params={
                    "sort": "trendingScore",
                    "direction": -1,
                    "limit": MAX_MODELS,
                    "full": "false",
                },
            )
            resp.raise_for_status()
        except Exception:
            logger.exception("HuggingFace models fetch failed")
            return []

        items = []
        for model in resp.json():
            model_id = model.get("id", "")
            if not model_id:
                continue

            last_modified = model.get("lastModified") or model.get("createdAt")
            published_at = None
            if last_modified:
                try:
                    published_at = datetime.fromisoformat(
                        last_modified.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            tags = model.get("tags", []) or []
            pipeline_tag = model.get("pipeline_tag", "")

            items.append(
                RawItemData(
                    source_id=f"model:{model_id}",
                    url=f"https://huggingface.co/{model_id}",
                    title=model_id,
                    content=f"Pipeline: {pipeline_tag}. Tags: {', '.join(tags[:10])}",
                    author=model_id.split("/")[0] if "/" in model_id else None,
                    published_at=published_at,
                    raw_metadata={
                        "type": "model",
                        "pipeline_tag": pipeline_tag,
                        "tags": tags[:20],
                        "downloads": model.get("downloads", 0),
                        "likes": model.get("likes", 0),
                        "trending_score": model.get("trendingScore", 0),
                    },
                )
            )
        return items

    async def _fetch_spaces(self, client: httpx.AsyncClient) -> list[RawItemData]:
        try:
            resp = await client.get(
                f"{HF_API}/spaces",
                params={
                    "sort": "trendingScore",
                    "direction": -1,
                    "limit": MAX_SPACES,
                    "full": "false",
                },
            )
            resp.raise_for_status()
        except Exception:
            logger.exception("HuggingFace spaces fetch failed")
            return []

        items = []
        for space in resp.json():
            space_id = space.get("id", "")
            if not space_id:
                continue

            last_modified = space.get("lastModified") or space.get("createdAt")
            published_at = None
            if last_modified:
                try:
                    published_at = datetime.fromisoformat(
                        last_modified.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            items.append(
                RawItemData(
                    source_id=f"space:{space_id}",
                    url=f"https://huggingface.co/spaces/{space_id}",
                    title=space_id,
                    content=space.get("cardData", {}).get("short_description", ""),
                    author=space_id.split("/")[0] if "/" in space_id else None,
                    published_at=published_at,
                    raw_metadata={
                        "type": "space",
                        "sdk": space.get("sdk", ""),
                        "likes": space.get("likes", 0),
                        "trending_score": space.get("trendingScore", 0),
                    },
                )
            )
        return items
