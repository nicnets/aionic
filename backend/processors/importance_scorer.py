"""
Importance scorer — fully deterministic, no LLM.

Score = weighted combination of:
  - source_weight  (from source_weights table, admin-editable)
  - freshness      (exponential decay over 72h)
  - engagement     (source-specific signals: stars, votes, points, etc.)
  - content_length (proxy for depth — longer = more signal)

Output: float 0.0–1.0. Items >= llm_importance_threshold (from system_config)
are eligible for expensive LLM enrichment (tagging, summarization).
"""
import math
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import RawItem, SourceWeight
from backend.db.system_config import get_config

logger = logging.getLogger(__name__)

# Freshness half-life in hours — score halves every N hours
FRESHNESS_HALF_LIFE_HOURS = 24.0

# Engagement signal extraction per source
# Returns a raw engagement count (normalized later)
def _extract_engagement(item: RawItem) -> float:
    meta = item.raw_metadata or {}
    source = item.source

    if source == "hn":
        points = meta.get("points", 0) or 0
        comments = meta.get("num_comments", 0) or 0
        return float(points + comments * 0.5)

    if source == "reddit":
        score = meta.get("score", 0) or 0
        comments = meta.get("num_comments", 0) or 0
        return float(max(score, 0) + comments * 0.3)

    if source == "github":
        stars = meta.get("stars", 0) or 0
        forks = meta.get("forks", 0) or 0
        return float(stars + forks * 2)

    if source == "stackoverflow":
        votes = meta.get("score", 0) or 0
        answers = meta.get("answer_count", 0) or 0
        views = (meta.get("view_count", 0) or 0) / 100
        return float(max(votes, 0) + answers * 2 + views)

    if source == "huggingface":
        downloads = (meta.get("downloads", 0) or 0) / 1000
        likes = meta.get("likes", 0) or 0
        trending = meta.get("trending_score", 0) or 0
        return float(downloads + likes + trending * 5)

    if source == "google_trends":
        return float(meta.get("avg_interest", 0) or 0)

    # rss, arxiv, newsapi — no reliable engagement signal
    return 0.0


def _normalize_engagement(raw: float, source: str) -> float:
    """Normalize engagement to 0–1 using per-source log scale."""
    if raw <= 0:
        return 0.0
    # Log normalization — 1000+ engagement → ~1.0 for most sources
    caps = {
        "hn": 2000,
        "reddit": 5000,
        "github": 50000,
        "stackoverflow": 1000,
        "huggingface": 10000,
        "google_trends": 100,
    }
    cap = caps.get(source, 500)
    return min(math.log1p(raw) / math.log1p(cap), 1.0)


def _freshness_score(published_at: datetime | None, collected_at: datetime) -> float:
    """Exponential decay from time of publication."""
    if published_at is None:
        return 0.5  # unknown age — neutral
    now = datetime.now(timezone.utc)
    # Use published_at if recent, else collected_at
    ref = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
    age_hours = max((now - ref).total_seconds() / 3600, 0)
    return math.exp(-math.log(2) * age_hours / FRESHNESS_HALF_LIFE_HOURS)


def _content_length_score(item: RawItem) -> float:
    """Short proxy for depth. Maxes out around 2000 chars."""
    total = len(item.title or "") + len(item.content or "")
    return min(total / 2000, 1.0)


async def score_item(item: RawItem, source_weight: float) -> float:
    """
    Compute importance score for a single RawItem.
    source_weight is the admin-configured weight for this source.
    """
    freshness = _freshness_score(item.published_at, item.collected_at)
    raw_eng = _extract_engagement(item)
    engagement = _normalize_engagement(raw_eng, item.source)
    depth = _content_length_score(item)

    # Weighted combination
    score = (
        source_weight * 0.40
        + freshness * 0.30
        + engagement * 0.20
        + depth * 0.10
    )
    return round(min(max(score, 0.0), 1.0), 4)


async def score_batch(
    items: list[RawItem],
    session: AsyncSession,
) -> dict[int, float]:
    """
    Score a batch of items. Loads source weights once from DB.
    Returns {raw_item_id: score}.
    """
    # Load all source weights into a lookup dict
    rows = await session.scalars(select(SourceWeight))
    weight_map: dict[str, float] = {sw.source: sw.weight for sw in rows}

    scores: dict[int, float] = {}
    for item in items:
        sw = weight_map.get(item.source, 1.0)
        scores[item.id] = await score_item(item, sw)

    return scores


async def is_llm_eligible(score: float, session: AsyncSession) -> bool:
    """True if this item should receive LLM enrichment."""
    threshold = float(await get_config(session, "llm_importance_threshold", "0.70"))
    return score >= threshold
