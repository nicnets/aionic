from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.api.schemas import OKResponse
from backend.db.system_config import get_config_dict

router = APIRouter(prefix="/collect", tags=["collect"])

COLLECTOR_MAP = {
    "rss": "backend.collectors.rss_collector.RSSCollector",
    "reddit": "backend.collectors.reddit_collector.RedditCollector",
    "hackernews": "backend.collectors.hackernews_collector.HackerNewsCollector",
    "arxiv": "backend.collectors.arxiv_collector.ArxivCollector",
    "github": "backend.collectors.github_collector.GitHubCollector",
    "huggingface": "backend.collectors.huggingface_collector.HuggingFaceCollector",
    "newsapi": "backend.collectors.newsapi_collector.NewsAPICollector",
    "google_trends": "backend.collectors.google_trends_collector.GoogleTrendsCollector",
    "stackoverflow": "backend.collectors.stackoverflow_collector.StackOverflowCollector",
}


async def _run_collector(dotted_path: str, config: dict[str, str]) -> None:
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib
    mod = importlib.import_module(module_path)
    collector_cls = getattr(mod, class_name)
    await collector_cls(config=config).collect()


@router.post("/all", response_model=OKResponse)
async def trigger_all(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger all collectors in the background."""
    config = await get_config_dict(db)
    for dotted_path in COLLECTOR_MAP.values():
        background_tasks.add_task(_run_collector, dotted_path, config)
    return OKResponse()


@router.post("/{source}", response_model=OKResponse)
async def trigger_source(
    source: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a single collector by name."""
    if source not in COLLECTOR_MAP:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown source '{source}'. Valid: {list(COLLECTOR_MAP.keys())}",
        )
    config = await get_config_dict(db)
    background_tasks.add_task(_run_collector, COLLECTOR_MAP[source], config)
    return OKResponse()
