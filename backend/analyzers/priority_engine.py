"""
Priority Engine — deterministic topic scoring.
Writes to the central topic_scores table — single source of truth
for all downstream features (suggestions, patterns, dashboard).

Score components (fully deterministic — no LLM):
  velocity_score    0.30  — mention acceleration: 3d vs prior 4d
  diversity_score   0.25  — distinct source count (weighted by source quality)
  weighted_score    0.20  — sum of source_weight × mentions per source
  consistency_score 0.15  — consecutive days with at least 1 mention
  momentum_score    0.10  — directional trend (positive only)

Classification thresholds:
  write_now  >= 0.65
  monitor    >= 0.35
  ignore      < 0.35
"""
import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.database import AsyncSessionLocal
from backend.db.models import Topic, TopicMention, TrendSnapshot, TopicScore, SourceWeight

logger = logging.getLogger(__name__)

WRITE_NOW_THRESHOLD = 0.65
MONITOR_THRESHOLD = 0.35


def _compute_score(
    mention_count_7d: int,
    mention_count_3d: int,
    source_count: int,
    source_weights_sum: float,
    consistency_days: int,
) -> tuple[float, dict, str, str]:
    """
    Pure function — no I/O.
    Returns (score, breakdown, classification, confidence_level).
    """
    # Velocity: 3-day acceleration vs baseline 4-day period
    prev_4d = max(mention_count_7d - mention_count_3d, 0)
    velocity = mention_count_3d / max(prev_4d, 1)
    velocity_score = min(velocity / 3.0, 1.0)  # 3x = max

    # Diversity: how many distinct sources
    diversity_score = min(source_count / 5.0, 1.0)

    # Weighted mentions: quality-adjusted
    weighted_score = min(source_weights_sum / 8.0, 1.0)

    # Consistency: consecutive days seen
    consistency_score = min(consistency_days / 7.0, 1.0)

    # Momentum: directional (only positive momentum contributes)
    prev_3d_est = prev_4d * 0.75  # rough 3-day equivalent of 4-day window
    if prev_3d_est > 0:
        momentum = (mention_count_3d - prev_3d_est) / prev_3d_est
    else:
        momentum = 1.0 if mention_count_3d > 0 else 0.0
    momentum_score = max(min(momentum, 1.0), 0.0)

    score = (
        velocity_score * 0.30
        + diversity_score * 0.25
        + weighted_score * 0.20
        + consistency_score * 0.15
        + momentum_score * 0.10
    )
    score = round(min(max(score, 0.0), 1.0), 4)

    if score >= WRITE_NOW_THRESHOLD:
        classification = "write_now"
    elif score >= MONITOR_THRESHOLD:
        classification = "monitor"
    else:
        classification = "ignore"

    if source_count >= 5 and consistency_days >= 3:
        confidence = "high"
    elif source_count >= 3 or consistency_days >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    breakdown = {
        "velocity": round(velocity_score, 3),
        "diversity": round(diversity_score, 3),
        "weighted_mentions": round(weighted_score, 3),
        "consistency": round(consistency_score, 3),
        "momentum": round(momentum_score, 3),
        "raw_7d": mention_count_7d,
        "raw_3d": mention_count_3d,
        "source_count": source_count,
        "source_weights_sum": round(source_weights_sum, 3),
    }

    return score, breakdown, classification, confidence


async def run_priority_engine(
    session: AsyncSession | None = None,
    log_fn=None,
) -> int:
    """
    Score all topics and write results to topic_scores.
    Returns count of topics scored.
    """
    if session is None:
        async with AsyncSessionLocal() as _session:
            return await run_priority_engine(_session, log_fn)

    def _log(msg: str):
        logger.info(msg)
        if log_fn:
            log_fn(msg)

    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_3d = now - timedelta(days=3)

    _log("Loading source weights...")
    sw_rows = await session.scalars(select(SourceWeight))
    weight_map: dict[str, float] = {sw.source: sw.weight for sw in sw_rows}

    _log("Loading approved topics...")
    topics = list(await session.scalars(select(Topic).where(Topic.is_approved == True)))  # noqa: E712
    if not topics:
        _log("No approved topics found — run the pipeline first to tag topics.")
        return 0

    _log(f"Scoring {len(topics)} topics over the last 7 days...")
    scored = 0
    write_now = monitor = ignore = 0

    for topic in topics:
        mentions_7d = list(await session.scalars(
            select(TopicMention).where(
                TopicMention.topic_id == topic.id,
                TopicMention.mentioned_at >= cutoff_7d,
            )
        ))

        mention_count_7d = len(mentions_7d)
        mention_count_3d = sum(1 for m in mentions_7d if m.mentioned_at >= cutoff_3d)

        sources_7d: dict[str, int] = {}
        for m in mentions_7d:
            sources_7d[m.source] = sources_7d.get(m.source, 0) + 1

        source_count = len(sources_7d)
        source_weights_sum = sum(
            weight_map.get(src, 1.0) * cnt
            for src, cnt in sources_7d.items()
        )

        days_with_mention = set()
        for m in mentions_7d:
            day = m.mentioned_at.date() if m.mentioned_at.tzinfo else m.mentioned_at.replace(tzinfo=timezone.utc).date()
            days_with_mention.add(day)

        consistency_days = 0
        check_day = now.date()
        for _ in range(7):
            if check_day in days_with_mention:
                consistency_days += 1
                check_day -= timedelta(days=1)
            else:
                break

        score, breakdown, classification, confidence = _compute_score(
            mention_count_7d=mention_count_7d,
            mention_count_3d=mention_count_3d,
            source_count=source_count,
            source_weights_sum=source_weights_sum,
            consistency_days=consistency_days,
        )

        if classification == "write_now":
            write_now += 1
        elif classification == "monitor":
            monitor += 1
        else:
            ignore += 1

        ts = TopicScore(
            topic_id=topic.id,
            computed_at=now,
            score=score,
            classification=classification,
            score_breakdown=breakdown,
            confidence_level=confidence,
            source_count=source_count,
            consistency_days=consistency_days,
        )
        session.add(ts)
        scored += 1

    await session.commit()
    _log(f"Scoring complete — {scored} topics scored.")
    _log(f"Results: {write_now} write now, {monitor} monitor, {ignore} ignore.")
    return scored
