"""
Performance learner — feedback loop.

Reads ContentPerformance records and adjusts source weights based on
which sources produced high-performing article signals.

Algorithm:
  1. For each ContentPerformance with engagement_score:
     - Trace back to ContentSuggestion → topic_ids → TopicMentions → sources
     - Build a source → [engagement_score] mapping
  2. Compute normalized adjustment per source (vs mean performance)
  3. Apply dampened adjustment to source weights (max ±10% per run)
  4. Record in source_weight_history

This creates a self-improving loop where sources that reliably produce
high-performing article ideas get a higher weight over time.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.database import AsyncSessionLocal
from backend.db.models import (
    ContentPerformance, ContentSuggestion, TopicMention,
    SourceWeight, SourceWeightHistory
)

logger = logging.getLogger(__name__)

# Maximum weight adjustment per run (±10%)
MAX_ADJUSTMENT = 0.10
# Minimum engagement score to consider (filters noise)
MIN_ENGAGEMENT = 0.1
# Dampening factor — how aggressively to apply adjustments
DAMPEN = 0.3
# Lookback window for performance data
LOOKBACK_DAYS = 90


async def run_performance_learner(session: AsyncSession | None = None) -> int:
    """
    Adjust source weights based on content performance.
    Returns count of source weights updated.
    """
    if session is None:
        async with AsyncSessionLocal() as _session:
            return await run_performance_learner(_session)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=LOOKBACK_DAYS)

    # Load performance records with engagement scores
    perf_rows = list(await session.scalars(
        select(ContentPerformance).where(
            ContentPerformance.recorded_at >= cutoff,
            ContentPerformance.engagement_score >= MIN_ENGAGEMENT,
        )
    ))

    if not perf_rows:
        logger.info("Performance learner: no performance data found")
        return 0

    # Map each performance record to the sources that generated the signal
    source_scores: dict[str, list[float]] = defaultdict(list)

    for perf in perf_rows:
        if not perf.suggestion_id:
            continue
        suggestion = await session.get(ContentSuggestion, perf.suggestion_id)
        if not suggestion or not suggestion.topic_ids:
            continue

        # Find which sources mentioned these topics
        mentions = list(await session.scalars(
            select(TopicMention).where(
                TopicMention.topic_id.in_(suggestion.topic_ids),
                TopicMention.mentioned_at >= cutoff,
            )
        ))
        sources_for_suggestion = {m.source for m in mentions}
        for src in sources_for_suggestion:
            source_scores[src].append(perf.engagement_score)

    if not source_scores:
        logger.info("Performance learner: no source-performance links found")
        return 0

    # Compute mean engagement per source
    source_means: dict[str, float] = {
        src: sum(scores) / len(scores)
        for src, scores in source_scores.items()
    }

    # Compute overall mean
    all_scores = [s for scores in source_scores.values() for s in scores]
    global_mean = sum(all_scores) / len(all_scores)

    # Adjust source weights
    updated = 0
    sw_rows = await session.scalars(select(SourceWeight))
    weight_map: dict[str, SourceWeight] = {sw.source: sw for sw in sw_rows}

    for src, mean_score in source_means.items():
        if src not in weight_map:
            continue

        sw = weight_map[src]
        if global_mean == 0:
            continue

        # Relative performance vs average
        relative = (mean_score - global_mean) / global_mean
        # Dampen and cap the adjustment
        adjustment = min(max(relative * DAMPEN, -MAX_ADJUSTMENT), MAX_ADJUSTMENT)

        if abs(adjustment) < 0.001:
            continue

        old_weight = sw.weight
        new_weight = round(min(max(old_weight + adjustment, 0.1), 2.0), 4)

        if new_weight == old_weight:
            continue

        history = SourceWeightHistory(
            source_weight_id=sw.id,
            old_weight=old_weight,
            new_weight=new_weight,
            reason=(
                f"Auto-adjusted: mean engagement {mean_score:.3f} "
                f"vs global mean {global_mean:.3f} "
                f"({len(source_scores[src])} data points)"
            ),
            changed_at=now,
        )
        session.add(history)
        sw.weight = new_weight
        updated += 1

    await session.commit()
    logger.info("Performance learner: updated %d source weights", updated)
    return updated
