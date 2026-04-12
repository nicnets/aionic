"""
Hype cycle detector.

Identifies topics that peaked in interest but are now declining —
the classic "peak of inflated expectations" pattern in AI coverage.

A topic is "hype_peak" when:
  - It had high mention counts 7-14 days ago (the peak)
  - Mentions in the last 7 days are significantly lower
  - The topic had cross-source coverage (not a single-source blip)

Also detects "recovery" — topics that dipped but are growing again.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.database import AsyncSessionLocal
from backend.db.models import Topic, TopicMention, Pattern

logger = logging.getLogger(__name__)

# Topic needs at least this many mentions in the peak window to qualify
MIN_PEAK_MENTIONS = 8
# Decline threshold: current window must be <= this fraction of peak
DECLINE_RATIO = 0.50
# Recovery threshold: current window must be >= this fraction of trough
RECOVERY_RATIO = 1.5
MIN_SOURCES_AT_PEAK = 2


async def detect_hype_peaks(session: AsyncSession | None = None) -> int:
    """
    Detect hype peaks and write Pattern records.
    Returns count of patterns written.
    """
    if session is None:
        async with AsyncSessionLocal() as _session:
            return await detect_hype_peaks(_session)

    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_14d = now - timedelta(days=14)
    cutoff_21d = now - timedelta(days=21)

    topics = list(await session.scalars(
        select(Topic).where(Topic.is_approved == True)  # noqa: E712
    ))

    written = 0

    for topic in topics:
        # Three windows: recent (0-7d), peak (7-14d), prior (14-21d)
        recent_mentions = list(await session.scalars(
            select(TopicMention).where(
                TopicMention.topic_id == topic.id,
                TopicMention.mentioned_at >= cutoff_7d,
            )
        ))
        peak_mentions = list(await session.scalars(
            select(TopicMention).where(
                TopicMention.topic_id == topic.id,
                TopicMention.mentioned_at >= cutoff_14d,
                TopicMention.mentioned_at < cutoff_7d,
            )
        ))
        prior_mentions = await session.scalar(
            select(func.count()).select_from(TopicMention).where(
                TopicMention.topic_id == topic.id,
                TopicMention.mentioned_at >= cutoff_21d,
                TopicMention.mentioned_at < cutoff_14d,
            )
        ) or 0

        peak_count = len(peak_mentions)
        recent_count = len(recent_mentions)

        if peak_count < MIN_PEAK_MENTIONS:
            continue

        peak_sources = {m.source for m in peak_mentions}
        if len(peak_sources) < MIN_SOURCES_AT_PEAK:
            continue

        # Check if already detected this pattern recently
        existing = await session.scalar(
            select(Pattern).where(
                Pattern.pattern_type.in_(["hype_peak", "hype_recovery"]),
                Pattern.detected_at >= cutoff_7d,
                func.array_position(Pattern.topic_ids, topic.id).isnot(None),
            )
        )
        if existing:
            continue

        # Hype peak: peak window had high activity, recent has dropped off
        if recent_count <= peak_count * DECLINE_RATIO:
            decline_pct = round((1 - recent_count / peak_count) * 100)
            evidence = {
                "peak_7d_14d": peak_count,
                "recent_0_7d": recent_count,
                "prior_14d_21d": prior_mentions,
                "peak_sources": list(peak_sources),
                "decline_pct": decline_pct,
            }
            confidence = min(peak_count / 20.0, 0.85)
            pattern = Pattern(
                pattern_type="hype_peak",
                title=f"Hype peak: {topic.name}",
                description=(
                    f"'{topic.name}' peaked with {peak_count} mentions across "
                    f"{len(peak_sources)} sources 7-14 days ago but has declined "
                    f"{decline_pct}% since — potential hype cycle."
                ),
                evidence=evidence,
                confidence_score=round(confidence, 3),
                detected_at=now,
                topic_ids=[topic.id],
            )
            session.add(pattern)
            written += 1

        # Hype recovery: topic dipped but is growing again
        elif (prior_mentions > 0
              and recent_count >= peak_count * RECOVERY_RATIO
              and recent_count >= peak_count):
            evidence = {
                "recent_count": recent_count,
                "peak_count": peak_count,
                "prior_count": prior_mentions,
                "growth_vs_peak": round(recent_count / peak_count, 2),
            }
            pattern = Pattern(
                pattern_type="hype_recovery",
                title=f"Hype recovery: {topic.name}",
                description=(
                    f"'{topic.name}' had a dip but is recovering with {recent_count} "
                    f"recent mentions — may signal lasting relevance."
                ),
                evidence=evidence,
                confidence_score=0.65,
                detected_at=now,
                topic_ids=[topic.id],
            )
            session.add(pattern)
            written += 1

    await session.commit()
    logger.info("Hype detector: wrote %d patterns", written)
    return written
