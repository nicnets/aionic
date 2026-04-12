from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from backend.api.deps import get_db
from backend.api.schemas import SystemStats
from backend.db.models import RawItem, Topic, Pattern, ContentSuggestion
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=SystemStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    total_items = await db.scalar(select(func.count(RawItem.id))) or 0
    items_today = await db.scalar(
        select(func.count(RawItem.id)).where(RawItem.collected_at >= today_start)
    ) or 0
    items_last_7d = await db.scalar(
        select(func.count(RawItem.id)).where(RawItem.collected_at >= week_ago)
    ) or 0
    total_topics = await db.scalar(select(func.count(Topic.id))) or 0
    active_topics = await db.scalar(
        select(func.count(Topic.id)).where(Topic.is_approved == True)  # noqa: E712
    ) or 0
    patterns_detected = await db.scalar(select(func.count(Pattern.id))) or 0
    suggestions_available = await db.scalar(
        select(func.count(ContentSuggestion.id)).where(ContentSuggestion.used == False)  # noqa: E712
    ) or 0

    sources = list(
        await db.scalars(
            select(RawItem.source)
            .distinct()
            .order_by(RawItem.source)
        )
    )

    last_item = await db.scalar(
        select(RawItem.collected_at).order_by(desc(RawItem.collected_at)).limit(1)
    )

    return SystemStats(
        total_items=total_items,
        items_today=items_today,
        items_last_7d=items_last_7d,
        total_topics=total_topics,
        active_topics=active_topics,
        patterns_detected=patterns_detected,
        suggestions_available=suggestions_available,
        sources_active=sources,
        last_collection_at=last_item,
    )
