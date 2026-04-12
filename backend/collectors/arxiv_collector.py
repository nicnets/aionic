"""
arXiv collector. Fetches recent papers from cs.AI, cs.LG, cs.CL, cs.CV
using the arXiv Atom feed API.
"""
import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from backend.collectors.base import BaseCollector, RawItemData

logger = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.RO"]
MAX_PER_CAT = 50
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _parse_arxiv_xml(xml_text: str) -> list[RawItemData]:
    root = ET.fromstring(xml_text)
    items = []
    for entry in root.findall("atom:entry", NS):
        arxiv_id_el = entry.find("atom:id", NS)
        if arxiv_id_el is None:
            continue
        full_id = arxiv_id_el.text or ""
        # Normalize to short ID: https://arxiv.org/abs/2301.12345 → 2301.12345
        source_id = full_id.split("/abs/")[-1].strip()

        title_el = entry.find("atom:title", NS)
        title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else None

        summary_el = entry.find("atom:summary", NS)
        summary = (summary_el.text or "").strip() if summary_el is not None else None

        published_el = entry.find("atom:published", NS)
        published_at = None
        if published_el is not None and published_el.text:
            try:
                published_at = datetime.fromisoformat(
                    published_el.text.replace("Z", "+00:00")
                )
            except ValueError:
                pass

        authors = [
            (a.find("atom:name", NS).text or "")
            for a in entry.findall("atom:author", NS)
            if a.find("atom:name", NS) is not None
        ]

        categories = [
            c.get("term", "")
            for c in entry.findall("atom:category", NS)
        ]

        link = f"https://arxiv.org/abs/{source_id}"

        items.append(
            RawItemData(
                source_id=source_id,
                url=link,
                title=title,
                content=summary,
                author=", ".join(authors[:5]),
                published_at=published_at,
                raw_metadata={"categories": categories, "authors": authors},
            )
        )
    return items


class ArxivCollector(BaseCollector):
    source_name = "arxiv"

    async def fetch_items(self) -> list[RawItemData]:
        async with httpx.AsyncClient(timeout=30) as client:
            tasks = [
                client.get(
                    ARXIV_API,
                    params={
                        "search_query": f"cat:{cat}",
                        "sortBy": "submittedDate",
                        "sortOrder": "descending",
                        "max_results": MAX_PER_CAT,
                    },
                )
                for cat in CATEGORIES
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

        all_items: list[RawItemData] = []
        seen: set[str] = set()

        for cat, resp in zip(CATEGORIES, responses):
            if isinstance(resp, Exception):
                logger.warning("arXiv fetch failed for %s: %s", cat, resp)
                continue
            try:
                resp.raise_for_status()
                for item in _parse_arxiv_xml(resp.text):
                    if item["source_id"] not in seen:
                        seen.add(item["source_id"])
                        all_items.append(item)
            except Exception:
                logger.exception("arXiv parse failed for %s", cat)

        return all_items
