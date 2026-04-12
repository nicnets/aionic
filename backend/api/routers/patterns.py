from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.api.deps import get_db
from backend.api.schemas import PatternOut
from backend.db.models import Pattern

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.get("", response_model=list[PatternOut])
async def list_patterns(
    pattern_type: str | None = Query(None, description="Filter by type, e.g. convergence"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    q = select(Pattern).order_by(desc(Pattern.detected_at)).limit(limit).offset(offset)
    if pattern_type:
        q = q.where(Pattern.pattern_type == pattern_type)
    rows = await db.scalars(q)
    return list(rows)


@router.get("/{pattern_id}", response_model=PatternOut)
async def get_pattern(pattern_id: int, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    row = await db.get(Pattern, pattern_id)
    if not row:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return row
