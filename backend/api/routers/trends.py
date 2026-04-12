from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from backend.api.deps import get_db
from backend.api.schemas import TrendingTopicOut, TopicTimeSeriesOut, TimeSeriesPoint, TopicItemOut, TopicSourceBreakdown
from backend.db.models import TopicScore, Topic, TrendSnapshot, TopicMention, RawItem

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("/current", response_model=list[TrendingTopicOut])
async def get_current_trends(
    limit: int = Query(20, ge=1, le=100),
    classification: str | None = Query(None, description="write_now | monitor | ignore"),
    db: AsyncSession = Depends(get_db),
):
    # Get latest score per topic
    subq = (
        select(
            TopicScore.topic_id,
            func.max(TopicScore.computed_at).label("max_at"),
        )
        .group_by(TopicScore.topic_id)
        .subquery()
    )
    q = (
        select(TopicScore, Topic)
        .join(subq, (TopicScore.topic_id == subq.c.topic_id) &
              (TopicScore.computed_at == subq.c.max_at))
        .join(Topic, TopicScore.topic_id == Topic.id)
        .order_by(desc(TopicScore.score))
        .limit(limit)
    )
    if classification:
        q = q.where(TopicScore.classification == classification)

    rows = await db.execute(q)
    results = []
    for ts, topic in rows:
        results.append(TrendingTopicOut(
            topic_id=topic.id,
            name=topic.name,
            slug=topic.slug,
            category=topic.category,
            score=ts.score,
            classification=ts.classification,
            confidence_level=ts.confidence_level,
            source_count=ts.source_count,
            consistency_days=ts.consistency_days,
            score_breakdown=ts.score_breakdown,
        ))
    return results


@router.get("/emerging", response_model=list[TrendingTopicOut])
async def get_emerging_trends(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    subq = (
        select(
            TopicScore.topic_id,
            func.max(TopicScore.computed_at).label("max_at"),
        )
        .group_by(TopicScore.topic_id)
        .subquery()
    )
    q = (
        select(TopicScore, Topic)
        .join(subq, (TopicScore.topic_id == subq.c.topic_id) &
              (TopicScore.computed_at == subq.c.max_at))
        .join(Topic, TopicScore.topic_id == Topic.id)
        .where(TopicScore.score_breakdown["pattern_type"].as_string() == "emerging")
        .order_by(desc(TopicScore.score))
        .limit(limit)
    )
    rows = await db.execute(q)
    results = []
    for ts, topic in rows:
        results.append(TrendingTopicOut(
            topic_id=topic.id,
            name=topic.name,
            slug=topic.slug,
            category=topic.category,
            score=ts.score,
            classification=ts.classification,
            confidence_level=ts.confidence_level,
            source_count=ts.source_count,
            consistency_days=ts.consistency_days,
            score_breakdown=ts.score_breakdown,
        ))
    return results


@router.get("/declining", response_model=list[TrendingTopicOut])
async def get_declining_trends(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    subq = (
        select(
            TopicScore.topic_id,
            func.max(TopicScore.computed_at).label("max_at"),
        )
        .group_by(TopicScore.topic_id)
        .subquery()
    )
    q = (
        select(TopicScore, Topic)
        .join(subq, (TopicScore.topic_id == subq.c.topic_id) &
              (TopicScore.computed_at == subq.c.max_at))
        .join(Topic, TopicScore.topic_id == Topic.id)
        .where(TopicScore.score_breakdown["momentum"].as_float() < 0)
        .order_by(TopicScore.score)
        .limit(limit)
    )
    rows = await db.execute(q)
    results = []
    for ts, topic in rows:
        results.append(TrendingTopicOut(
            topic_id=topic.id,
            name=topic.name,
            slug=topic.slug,
            category=topic.category,
            score=ts.score,
            classification=ts.classification,
            confidence_level=ts.confidence_level,
            source_count=ts.source_count,
            consistency_days=ts.consistency_days,
            score_breakdown=ts.score_breakdown,
        ))
    return results


@router.get("/{slug}/timeseries", response_model=TopicTimeSeriesOut)
async def get_topic_timeseries(
    slug: str,
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
):
    topic = await db.scalar(select(Topic).where(Topic.slug == slug))
    if not topic:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Topic not found")

    since = date.today() - timedelta(days=days)
    snapshots = await db.scalars(
        select(TrendSnapshot)
        .where(
            TrendSnapshot.topic_id == topic.id,
            TrendSnapshot.snapshot_date >= since,
        )
        .order_by(TrendSnapshot.snapshot_date)
    )

    data = [
        TimeSeriesPoint(
            snapshot_date=s.snapshot_date,
            mention_count=s.mention_count,
            weighted_mention_count=s.weighted_mention_count,
            momentum_score=s.momentum_score,
            sentiment_avg=s.sentiment_avg,
            sources=s.sources,
        )
        for s in snapshots
    ]

    return TopicTimeSeriesOut(topic_id=topic.id, name=topic.name, slug=topic.slug, data=data)


@router.get("/{slug}/items", response_model=list[TopicItemOut])
async def get_topic_items(
    slug: str,
    limit: int = Query(50, ge=1, le=200),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Recent raw items tagged with this topic, newest first."""
    from datetime import datetime, timedelta, timezone
    topic = await db.scalar(select(Topic).where(Topic.slug == slug))
    if not topic:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Topic not found")

    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await db.execute(
        select(RawItem)
        .join(TopicMention, TopicMention.raw_item_id == RawItem.id)
        .where(TopicMention.topic_id == topic.id, TopicMention.mentioned_at >= since)
        .order_by(RawItem.published_at.desc().nullslast())
        .limit(limit)
    )
    items = rows.scalars().all()
    return [
        TopicItemOut(
            id=item.id,
            source=item.source,
            title=item.title,
            url=item.url,
            author=item.author,
            published_at=item.published_at,
            importance_score=item.importance_score,
        )
        for item in items
    ]


@router.get("/{slug}/sources", response_model=list[TopicSourceBreakdown])
async def get_topic_sources(
    slug: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Per-source mention counts for this topic over the last N days."""
    from datetime import datetime, timedelta, timezone
    topic = await db.scalar(select(Topic).where(Topic.slug == slug))
    if not topic:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Topic not found")

    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await db.execute(
        select(TopicMention.source, func.count(TopicMention.id).label("cnt"))
        .where(TopicMention.topic_id == topic.id, TopicMention.mentioned_at >= since)
        .group_by(TopicMention.source)
        .order_by(func.count(TopicMention.id).desc())
    )
    return [TopicSourceBreakdown(source=r.source, mention_count=r.cnt) for r in rows]
