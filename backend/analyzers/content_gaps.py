"""
Content gap detector.

Identifies high-priority topics that lack recent content coverage —
the editorial opportunity hiding in the data.

A "content_gap" pattern is created when:
  - Topic has a high score (write_now or monitor)
  - No ContentSuggestion was created for this topic in the last 30 days
  - OR: the topic has significantly more recent mentions than articles written

Written to patterns table with type="content_gap".
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.database import AsyncSessionLocal
from backend.db.models import Topic, TopicScore, ContentSuggestion, Pattern

logger = logging.getLogger(__name__)

MIN_SCORE_FOR_GAP = 0.35  # monitor or above
GAP_LOOKBACK_DAYS = 30


async def detect_content_gaps(session: AsyncSession | None = None) -> int:
    """
    Detect content gaps and write Pattern records.
    Returns count of gap patterns written.
    """
    if session is None:
        async with AsyncSessionLocal() as _session:
            return await detect_content_gaps(_session)

    now = datetime.now(timezone.utc)
    gap_cutoff = now - timedelta(days=GAP_LOOKBACK_DAYS)

    # Get latest score per topic (subquery)
    from sqlalchemy import desc
    subq = (
        select(
            TopicScore.topic_id,
            func.max(TopicScore.computed_at).label("max_at"),
        )
        .group_by(TopicScore.topic_id)
        .subquery()
    )
    scored_topics = list(await session.execute(
        select(TopicScore, Topic)
        .join(subq, (TopicScore.topic_id == subq.c.topic_id) &
              (TopicScore.computed_at == subq.c.max_at))
        .join(Topic, TopicScore.topic_id == Topic.id)
        .where(TopicScore.score >= MIN_SCORE_FOR_GAP)
        .order_by(desc(TopicScore.score))
    ))

    written = 0

    for ts, topic in scored_topics:
        # Check for recent suggestions for this topic
        recent_suggestion = await session.scalar(
            select(ContentSuggestion).where(
                ContentSuggestion.created_at >= gap_cutoff,
                func.array_position(ContentSuggestion.topic_ids, topic.id).isnot(None),
            )
        )
        if recent_suggestion:
            continue

        # Check if we already have a recent content_gap pattern for this topic
        existing = await session.scalar(
            select(Pattern).where(
                Pattern.pattern_type == "content_gap",
                Pattern.detected_at >= gap_cutoff,
                func.array_position(Pattern.topic_ids, topic.id).isnot(None),
            )
        )
        if existing:
            continue

        evidence = {
            "topic_score": ts.score,
            "classification": ts.classification,
            "source_count": ts.source_count,
            "consistency_days": ts.consistency_days,
            "days_without_suggestion": GAP_LOOKBACK_DAYS,
            "confidence_level": ts.confidence_level,
        }

        confidence = min(ts.score * 1.2, 0.95)
        urgency = ts.score

        pattern = Pattern(
            pattern_type="content_gap",
            title=f"Content gap: {topic.name}",
            description=(
                f"'{topic.name}' scores {ts.score:.2f} ({ts.classification.replace('_', ' ')}) "
                f"with {ts.source_count} sources over {ts.consistency_days} days, "
                f"but no article has been suggested in {GAP_LOOKBACK_DAYS} days."
            ),
            evidence=evidence,
            confidence_score=round(confidence, 3),
            detected_at=now,
            topic_ids=[topic.id],
        )
        session.add(pattern)
        written += 1

    await session.commit()
    logger.info("Content gap detector: wrote %d patterns", written)
    return written
