from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from backend.api.deps import get_db
from backend.api.schemas import RawItemOut
from backend.db.models import RawItem

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[str])
async def list_sources(db: AsyncSession = Depends(get_db)):
    """Return all distinct source names seen in raw_items."""
    rows = await db.scalars(select(RawItem.source).distinct().order_by(RawItem.source))
    return list(rows)


@router.get("/{source}/items", response_model=list[RawItemOut])
async def get_source_items(
    source: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(RawItem)
        .where(RawItem.source == source)
        .order_by(desc(RawItem.collected_at))
        .limit(limit)
        .offset(offset)
    )
    return list(rows)


@router.get("/{source}/stats")
async def get_source_stats(source: str, db: AsyncSession = Depends(get_db)):
    total = await db.scalar(
        select(func.count(RawItem.id)).where(RawItem.source == source)
    )
    processed = await db.scalar(
        select(func.count(RawItem.id)).where(
            RawItem.source == source, RawItem.processed == True  # noqa: E712
        )
    )
    return {
        "source": source,
        "total_items": total or 0,
        "processed_items": processed or 0,
        "pending_items": (total or 0) - (processed or 0),
    }
