from fastapi import APIRouter

from backend.api.routers.health import router as health_router
from backend.api.routers.trends import router as trends_router
from backend.api.routers.patterns import router as patterns_router
from backend.api.routers.suggestions import router as suggestions_router
from backend.api.routers.sources import router as sources_router
from backend.api.routers.search import router as search_router
from backend.api.routers.admin import router as admin_router
from backend.api.routers.collect import router as collect_router
from backend.api.routers.stats import router as stats_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(trends_router)
api_router.include_router(patterns_router)
api_router.include_router(suggestions_router)
api_router.include_router(sources_router)
api_router.include_router(search_router)
api_router.include_router(admin_router)
api_router.include_router(collect_router)
api_router.include_router(stats_router)
