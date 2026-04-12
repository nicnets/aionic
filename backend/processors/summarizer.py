"""
Summarizer: generates concise summaries and extracts topic tags via LLM.
Only called for items that pass the importance threshold (top ~30%).

One LLM call per item returns:
  - summary (2–3 sentences)
  - topics (list of topic strings for the tagger)
  - category (research | tools | applications | news | community)
  - sentiment (-1.0 to 1.0)

Results are cached via the LLM cache in ai/provider.py.
"""
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import RawItem
from backend import ai

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an AI content analyst. Given a piece of AI-related content, "
    "extract structured metadata. Respond ONLY with valid JSON — no markdown, no explanation."
)

PROMPT_TEMPLATE = """\
Analyze this AI content and return JSON with these exact keys:

{{
  "summary": "2-3 sentence summary of the key insight",
  "topics": ["list", "of", "specific", "ai", "topics", "mentioned"],
  "category": "one of: research | tools | applications | news | community",
  "sentiment": 0.0
}}

sentiment range: -1.0 (very negative) to 1.0 (very positive), 0.0 = neutral.

Content:
Title: {title}
Body: {body}
"""


async def enrich_item(
    item: RawItem,
    session: AsyncSession,
) -> dict | None:
    """
    Call the LLM to summarize and tag a single item.
    Returns the parsed JSON dict or None on failure.
    """
    title = (item.title or "").strip()
    body = (item.content or "").strip()[:3000]

    if not title and not body:
        return None

    prompt = PROMPT_TEMPLATE.format(title=title, body=body)

    try:
        raw = await ai.provider.complete(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            session=session,
            use_cache=True,
        )
        result = _parse_response(raw)
        return result
    except Exception:
        logger.exception("Summarizer LLM call failed for item %d", item.id)
        return None


def _parse_response(raw: str) -> dict | None:
    """Parse JSON from LLM response. Robust to minor formatting issues."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object within the response
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return None

    return {
        "summary": str(data.get("summary", ""))[:1000],
        "topics": [str(t) for t in (data.get("topics") or [])[:15]],
        "category": str(data.get("category", "news")),
        "sentiment": float(data.get("sentiment", 0.0)),
    }


async def enrich_batch(
    items: list[RawItem],
    session: AsyncSession,
) -> dict[int, dict | None]:
    """
    Enrich a batch of items. Returns {item_id: enrichment_dict | None}.
    Calls LLM sequentially — each call is independently cached.
    """
    results: dict[int, dict | None] = {}
    for item in items:
        results[item.id] = await enrich_item(item, session)
    return results
