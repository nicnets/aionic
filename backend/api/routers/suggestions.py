from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.api.deps import get_db
from backend.api.schemas import ContentSuggestionOut, OKResponse
from backend.db.models import ContentSuggestion

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


@router.get("", response_model=list[ContentSuggestionOut])
async def list_suggestions(
    unused_only: bool = Query(True, description="Return only unused suggestions"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(ContentSuggestion).order_by(desc(ContentSuggestion.urgency_score)).limit(limit)
    if unused_only:
        q = q.where(ContentSuggestion.used == False)  # noqa: E712
    rows = await db.scalars(q)
    return list(rows)


@router.get("/{suggestion_id}", response_model=ContentSuggestionOut)
async def get_suggestion(suggestion_id: int, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    row = await db.get(ContentSuggestion, suggestion_id)
    if not row:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return row


@router.post("/{suggestion_id}/use", response_model=OKResponse)
async def mark_suggestion_used(suggestion_id: int, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    row = await db.get(ContentSuggestion, suggestion_id)
    if not row:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    row.used = True
    await db.commit()
    return OKResponse()
