"""
Scheduler: wires all collection, processing, and analysis jobs into APScheduler.

Intervals are loaded from system_config at startup. To apply new intervals,
restart the application (or use the admin "Restart Scheduler" control).
"""
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Async job wrappers
# ---------------------------------------------------------------------------

async def _collect(dotted_path: str, config: dict[str, str]) -> None:
    import importlib
    module_path, class_name = dotted_path.rsplit(".", 1)
    try:
        mod = importlib.import_module(module_path)
        collector_cls = getattr(mod, class_name)
        count = await collector_cls(config=config).collect()
        logger.info("Collector %s: %d new items", class_name, count)
    except Exception:
        logger.exception("Collector %s failed", class_name)


async def _run_pipeline() -> None:
    try:
        from backend.processors.pipeline import run_pipeline
        count = await run_pipeline()
        logger.info("Pipeline: processed %d items", count)
    except Exception:
        logger.exception("Pipeline failed")


async def _run_priority_engine() -> None:
    try:
        from backend.analyzers.priority_engine import run_priority_engine
        count = await run_priority_engine()
        logger.info("Priority engine: scored %d topics", count)
    except Exception:
        logger.exception("Priority engine failed")


async def _run_patterns() -> None:
    try:
        from backend.analyzers.emergence import detect_emerging
        from backend.analyzers.cross_source import detect_cross_source
        from backend.analyzers.hype_detector import detect_hype_peaks
        from backend.analyzers.content_gaps import detect_content_gaps

        e = await detect_emerging()
        c = await detect_cross_source()
        h = await detect_hype_peaks()
        g = await detect_content_gaps()
        logger.info("Patterns: emerging=%d cross=%d hype=%d gaps=%d", e, c, h, g)
    except Exception:
        logger.exception("Pattern detection failed")


async def _run_snapshots() -> None:
    try:
        from backend.analyzers.trend_detector import take_daily_snapshot
        count = await take_daily_snapshot()
        logger.info("Trend snapshots: created %d", count)
    except Exception:
        logger.exception("Trend snapshot failed")


async def _run_suggestions() -> None:
    try:
        from backend.analyzers.suggestion_generator import generate_suggestions
        count = await generate_suggestions()
        logger.info("Suggestion generator: wrote %d suggestions", count)
    except Exception:
        logger.exception("Suggestion generator failed")


async def _run_performance_learner() -> None:
    try:
        from backend.analyzers.performance_learner import run_performance_learner
        count = await run_performance_learner()
        logger.info("Performance learner: updated %d weights", count)
    except Exception:
        logger.exception("Performance learner failed")


def _job(coro_fn):
    """Create a sync callable that schedules the coroutine on the running loop."""
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        loop.create_task(coro_fn(*args, **kwargs))
    return wrapper


def _cfg_int(config: dict[str, str], key: str, default: int) -> int:
    try:
        return int(config.get(key, default))
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------

def start_scheduler(config: dict[str, str]) -> AsyncIOScheduler:
    """
    Build and start the APScheduler instance.
    `config` is a snapshot from get_config_dict() loaded at startup.
    Interval changes in the admin panel take effect after the next restart.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    # --- Collectors ---
    scheduler.add_job(
        _job(lambda: _collect("backend.collectors.rss_collector.RSSCollector", config)),
        IntervalTrigger(hours=_cfg_int(config, "collect_rss_interval_hours", 1)),
        id="collect_rss", replace_existing=True,
    )
    scheduler.add_job(
        _job(lambda: _collect("backend.collectors.reddit_collector.RedditCollector", config)),
        IntervalTrigger(hours=_cfg_int(config, "collect_reddit_interval_hours", 2)),
        id="collect_reddit", replace_existing=True,
    )
    scheduler.add_job(
        _job(lambda: _collect("backend.collectors.hackernews_collector.HackerNewsCollector", config)),
        IntervalTrigger(hours=_cfg_int(config, "collect_hn_interval_hours", 2)),
        id="collect_hn", replace_existing=True,
    )
    scheduler.add_job(
        _job(lambda: _collect("backend.collectors.newsapi_collector.NewsAPICollector", config)),
        IntervalTrigger(hours=_cfg_int(config, "collect_newsapi_interval_hours", 4)),
        id="collect_newsapi", replace_existing=True,
    )
    scheduler.add_job(
        _job(lambda: _collect("backend.collectors.github_collector.GitHubCollector", config)),
        IntervalTrigger(hours=_cfg_int(config, "collect_github_interval_hours", 4)),
        id="collect_github", replace_existing=True,
    )
    scheduler.add_job(
        _job(lambda: _collect("backend.collectors.arxiv_collector.ArxivCollector", config)),
        IntervalTrigger(hours=_cfg_int(config, "collect_arxiv_interval_hours", 6)),
        id="collect_arxiv", replace_existing=True,
    )
    scheduler.add_job(
        _job(lambda: _collect("backend.collectors.huggingface_collector.HuggingFaceCollector", config)),
        IntervalTrigger(hours=_cfg_int(config, "collect_huggingface_interval_hours", 6)),
        id="collect_huggingface", replace_existing=True,
    )
    scheduler.add_job(
        _job(lambda: _collect("backend.collectors.stackoverflow_collector.StackOverflowCollector", config)),
        IntervalTrigger(hours=_cfg_int(config, "collect_stackoverflow_interval_hours", 6)),
        id="collect_stackoverflow", replace_existing=True,
    )
    scheduler.add_job(
        _job(lambda: _collect("backend.collectors.google_trends_collector.GoogleTrendsCollector", config)),
        CronTrigger(hour=_cfg_int(config, "collect_google_trends_cron_hour", 2), minute=30),
        id="collect_google_trends", replace_existing=True,
    )

    # --- Processing ---
    scheduler.add_job(
        _job(_run_pipeline),
        IntervalTrigger(minutes=30),
        id="pipeline", replace_existing=True,
    )

    # --- Analysis ---
    scheduler.add_job(
        _job(_run_priority_engine),
        IntervalTrigger(hours=1),
        id="priority_engine", replace_existing=True,
    )
    scheduler.add_job(
        _job(_run_patterns),
        IntervalTrigger(hours=2),
        id="pattern_detection", replace_existing=True,
    )
    scheduler.add_job(
        _job(_run_snapshots),
        CronTrigger(hour=0, minute=5),
        id="trend_snapshots", replace_existing=True,
    )
    scheduler.add_job(
        _job(_run_suggestions),
        IntervalTrigger(hours=6),
        id="suggestion_generator", replace_existing=True,
    )
    scheduler.add_job(
        _job(_run_performance_learner),
        CronTrigger(hour=3, minute=0),
        id="performance_learner", replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))
    return scheduler
