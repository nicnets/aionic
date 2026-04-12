"""
Trend detector: creates daily TrendSnapshot records for each topic.
Run once per day (scheduler calls this at midnight UTC).

Each snapshot captures:
  - mention_count: raw mentions that day
  - weighted_mention_count: source-weighted sum
  - sources: list of sources that mentioned the topic
  - momentum_score: normalized day-over-day change
  - sentiment_avg: average sentiment from ProcessedItems
"""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.database import AsyncSessionLocal
from backend.db.models import (
    Topic, TopicMention, TrendSnapshot, SourceWeight, ProcessedItem, RawItem
)

logger = logging.getLogger(__name__)


async def take_daily_snapshot(
    snapshot_date: date | None = None,
    session: AsyncSession | None = None,
) -> int:
    """
    Create TrendSnapshot rows for all topics for the given date (default: yesterday).
    Skips topics that already have a snapshot for that date.
    Returns count of snapshots created.
    """
    if session is None:
        async with AsyncSessionLocal() as _session:
            return await take_daily_snapshot(snapshot_date, _session)

    if snapshot_date is None:
        snapshot_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    day_start = datetime.combine(snapshot_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    # Load source weights
    sw_rows = await session.scalars(select(SourceWeight))
    weight_map: dict[str, float] = {sw.source: sw.weight for sw in sw_rows}

    topics = list(await session.scalars(select(Topic).where(Topic.is_approved == True)))  # noqa: E712
    created = 0

    for topic in topics:
        # Skip if already exists
        existing = await session.scalar(
            select(TrendSnapshot).where(
                TrendSnapshot.topic_id == topic.id,
                TrendSnapshot.snapshot_date == snapshot_date,
            )
        )
        if existing:
            continue

        # Get all mentions for this day
        mentions = list(await session.scalars(
            select(TopicMention).where(
                TopicMention.topic_id == topic.id,
                TopicMention.mentioned_at >= day_start,
                TopicMention.mentioned_at < day_end,
            )
        ))

        if not mentions:
            continue  # no activity — don't create empty snapshot

        mention_count = len(mentions)
        sources = list({m.source for m in mentions})
        weighted = sum(weight_map.get(m.source, 1.0) for m in mentions)

        # Sentiment: average from ProcessedItems for raw_items in this day
        raw_item_ids = [m.raw_item_id for m in mentions]
        sentiment_avg = None
        if raw_item_ids:
            result = await session.scalar(
                select(func.avg(ProcessedItem.sentiment_score)).where(
                    ProcessedItem.raw_item_id.in_(raw_item_ids),
                    ProcessedItem.sentiment_score.is_not(None),
                )
            )
            if result is not None:
                sentiment_avg = round(float(result), 4)

        # Momentum: compare to previous snapshot
        prev_snapshot = await session.scalar(
            select(TrendSnapshot).where(
                TrendSnapshot.topic_id == topic.id,
                TrendSnapshot.snapshot_date < snapshot_date,
            ).order_by(TrendSnapshot.snapshot_date.desc())
        )
        momentum_score = None
        if prev_snapshot and prev_snapshot.mention_count > 0:
            delta = mention_count - prev_snapshot.mention_count
            momentum_score = round(delta / prev_snapshot.mention_count, 4)

        snap = TrendSnapshot(
            topic_id=topic.id,
            snapshot_date=snapshot_date,
            mention_count=mention_count,
            weighted_mention_count=round(weighted, 4),
            sources=sources,
            momentum_score=momentum_score,
            sentiment_avg=sentiment_avg,
        )
        session.add(snap)
        created += 1

    await session.commit()
    logger.info("Trend detector: created %d snapshots for %s", created, snapshot_date)
    return created


async def backfill_snapshots(
    days: int = 30,
    session: AsyncSession | None = None,
    log_fn=None,
) -> int:
    """Backfill snapshots for the last N days. Useful on first run."""
    if session is None:
        async with AsyncSessionLocal() as _session:
            return await backfill_snapshots(days, _session, log_fn)

    def _log(msg: str):
        logger.info(msg)
        if log_fn:
            log_fn(msg)

    _log(f"Backfilling trend snapshots for the last {days} days...")
    total = 0
    today = datetime.now(timezone.utc).date()
    for i in range(1, days + 1):
        d = today - timedelta(days=i)
        total += await take_daily_snapshot(d, session)
    _log(f"Backfill complete — {total} snapshots created.")
    return total
