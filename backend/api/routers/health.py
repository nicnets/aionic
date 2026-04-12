from fastapi import APIRouter
from backend.api.schemas import OKResponse

router = APIRouter()


@router.get("/health", response_model=OKResponse)
async def health():
    return OKResponse()
