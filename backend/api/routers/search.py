from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc

from backend.api.deps import get_db
from backend.api.schemas import RawItemOut, TopicOut
from backend.db.models import RawItem, Topic

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/topics", response_model=list[TopicOut])
async def search_topics(
    q: str = Query(..., min_length=2, description="Search term"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    term = f"%{q.lower()}%"
    rows = await db.scalars(
        select(Topic)
        .where(
            or_(
                Topic.name.ilike(term),
                Topic.slug.ilike(term),
            )
        )
        .order_by(Topic.name)
        .limit(limit)
    )
    return list(rows)


@router.get("/items", response_model=list[RawItemOut])
async def search_items(
    q: str = Query(..., min_length=2, description="Search term"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    term = f"%{q.lower()}%"
    rows = await db.scalars(
        select(RawItem)
        .where(
            or_(
                RawItem.title.ilike(term),
                RawItem.content.ilike(term),
            )
        )
        .order_by(desc(RawItem.collected_at))
        .limit(limit)
    )
    return list(rows)
