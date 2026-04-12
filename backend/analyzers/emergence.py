"""
Emergence detector: identifies newly emerging topics.

A topic is "emerging" when:
  - It has appeared in the last 7 days
  - Its 7-day mention count is >= 3x its prior 7-day count (or it's brand-new)
  - It appears in at least 2 distinct sources

Detected patterns are written to the patterns table with type="emerging".
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.database import AsyncSessionLocal
from backend.db.models import Topic, TopicMention, Pattern

logger = logging.getLogger(__name__)

MIN_SOURCES = 2
EMERGENCE_MULTIPLIER = 3.0  # 3x mention growth = emerging


async def detect_emerging(session: AsyncSession | None = None) -> int:
    """
    Detect emerging topics and write Pattern records.
    Returns count of emerging patterns written.
    """
    if session is None:
        async with AsyncSessionLocal() as _session:
            return await detect_emerging(_session)

    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_14d = now - timedelta(days=14)

    topics = list(await session.scalars(
        select(Topic).where(Topic.is_approved == True)  # noqa: E712
    ))

    written = 0

    for topic in topics:
        # Recent 7 days
        recent_mentions = list(await session.scalars(
            select(TopicMention).where(
                TopicMention.topic_id == topic.id,
                TopicMention.mentioned_at >= cutoff_7d,
            )
        ))
        if not recent_mentions:
            continue

        recent_count = len(recent_mentions)
        recent_sources = {m.source for m in recent_mentions}
        if len(recent_sources) < MIN_SOURCES:
            continue

        # Prior 7 days (7-14 days ago)
        prior_mentions = await session.scalar(
            select(func.count()).select_from(TopicMention).where(
                TopicMention.topic_id == topic.id,
                TopicMention.mentioned_at >= cutoff_14d,
                TopicMention.mentioned_at < cutoff_7d,
            )
        ) or 0

        # Determine if emerging
        is_new = prior_mentions == 0
        is_accelerating = prior_mentions > 0 and recent_count >= prior_mentions * EMERGENCE_MULTIPLIER

        if not (is_new or is_accelerating):
            continue

        # Check if we already have a recent emergence pattern for this topic
        existing = await session.scalar(
            select(Pattern).where(
                Pattern.pattern_type == "emerging",
                Pattern.detected_at >= cutoff_7d,
                func.array_position(Pattern.topic_ids, topic.id).isnot(None),
            )
        )
        if existing:
            continue

        evidence = {
            "recent_7d": recent_count,
            "prior_7d": prior_mentions,
            "sources": list(recent_sources),
            "is_brand_new": is_new,
            "growth_ratio": round(recent_count / max(prior_mentions, 1), 2),
        }
        confidence = 0.9 if is_new and recent_count >= 5 else (
            0.7 if is_accelerating else 0.5
        )

        pattern = Pattern(
            pattern_type="emerging",
            title=f"Emerging topic: {topic.name}",
            description=(
                f"'{topic.name}' is newly emerging with {recent_count} mentions "
                f"across {len(recent_sources)} sources in the last 7 days"
                + (f" (up from {prior_mentions} in the prior period)" if prior_mentions else "")
                + "."
            ),
            evidence=evidence,
            confidence_score=confidence,
            detected_at=now,
            topic_ids=[topic.id],
        )
        session.add(pattern)
        written += 1

    await session.commit()
    logger.info("Emergence detector: wrote %d patterns", written)
    return written
