import traceback
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.api.deps import get_db
from backend.api.schemas import (
    SourceWeightOut, SourceWeightUpdate,
    AIProviderOut, AIProviderUpdate,
    TopicOut, UnresolvedTopicOut,
    PerformanceSubmit, OKResponse,
    SystemConfigOut, SystemConfigUpdate,
    JobStatusOut, LogEntryOut,
    RssFeedOut, RssFeedCreate, RssFeedUpdate, RssFeedTestResult,
)
from backend.db.models import (
    SourceWeight, SourceWeightHistory,
    AIProviderConfig, Topic, UnresolvedTopic, ContentPerformance,
    SystemConfig, RssFeed,
)

_MASKED = "••••••••"

# ---------------------------------------------------------------------------
# In-memory job state (single-process — fine for this use case)
# ---------------------------------------------------------------------------

_JOB_NAMES = ("pipeline", "analysis", "suggestions")

_jobs: dict[str, dict] = {
    name: {"status": "idle", "logs": [], "started_at": None, "finished_at": None}
    for name in _JOB_NAMES
}


def _make_logger(job: str):
    """Return a log_fn that appends timestamped entries to the job's log list."""
    def log_fn(msg: str):
        _jobs[job]["logs"].append({
            "t": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "msg": msg,
        })
    return log_fn


def _start(job: str):
    _jobs[job]["status"] = "running"
    _jobs[job]["logs"] = []
    _jobs[job]["started_at"] = datetime.now(timezone.utc).isoformat()
    _jobs[job]["finished_at"] = None
    _make_logger(job)(f"Starting {job}...")


def _finish(job: str):
    _jobs[job]["status"] = "done"
    _jobs[job]["finished_at"] = datetime.now(timezone.utc).isoformat()


def _fail(job: str, err: str, tb: str = ""):
    _jobs[job]["status"] = "error"
    _jobs[job]["finished_at"] = datetime.now(timezone.utc).isoformat()
    log = _make_logger(job)
    log(f"ERROR: {err}")
    if tb:
        for line in tb.strip().splitlines():
            log(f"  {line}")

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# System logs
# ---------------------------------------------------------------------------

@router.get("/logs", response_model=list[LogEntryOut])
async def get_logs(
    level: str | None = Query(default=None),
    limit: int = Query(default=500, le=1000),
):
    from backend.log_store import get_logs
    return get_logs(level=level, limit=limit)


@router.post("/logs/clear", response_model=OKResponse)
async def clear_logs():
    from backend.log_store import clear
    clear()
    return OKResponse()


# ---------------------------------------------------------------------------
# System config
# ---------------------------------------------------------------------------

@router.get("/config", response_model=list[SystemConfigOut])
async def list_config(db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(SystemConfig).order_by(SystemConfig.category, SystemConfig.key))
    result = []
    for row in rows:
        result.append(SystemConfigOut(
            key=row.key,
            value=_MASKED if (row.is_secret and row.value) else row.value,
            is_secret=row.is_secret,
            category=row.category,
            description=row.description,
            updated_at=row.updated_at,
        ))
    return result


@router.put("/config/{key}", response_model=SystemConfigOut)
async def update_config(
    key: str,
    body: SystemConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    row = await db.scalar(select(SystemConfig).where(SystemConfig.key == key))
    if not row:
        raise HTTPException(status_code=404, detail=f"Config key '{key}' not found")
    row.value = body.value
    await db.commit()
    await db.refresh(row)
    return SystemConfigOut(
        key=row.key,
        value=_MASKED if (row.is_secret and row.value) else row.value,
        is_secret=row.is_secret,
        category=row.category,
        description=row.description,
        updated_at=row.updated_at,
    )


# ---------------------------------------------------------------------------
# Source weights
# ---------------------------------------------------------------------------

@router.get("/weights", response_model=list[SourceWeightOut])
async def list_weights(db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(SourceWeight).order_by(SourceWeight.source))
    return list(rows)


@router.put("/weights/{source}", response_model=SourceWeightOut)
async def update_weight(
    source: str,
    body: SourceWeightUpdate,
    db: AsyncSession = Depends(get_db),
):
    row = await db.scalar(select(SourceWeight).where(SourceWeight.source == source))
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")

    history = SourceWeightHistory(
        source_weight_id=row.id,
        old_weight=row.weight,
        new_weight=body.weight,
    )
    db.add(history)
    row.weight = body.weight
    await db.commit()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# AI provider config
# ---------------------------------------------------------------------------

@router.get("/provider", response_model=list[AIProviderOut])
async def list_providers(db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(AIProviderConfig).order_by(AIProviderConfig.provider))
    return list(rows)


@router.put("/provider/active", response_model=AIProviderOut)
async def set_active_provider(body: AIProviderUpdate, db: AsyncSession = Depends(get_db)):
    # Deactivate all, then activate the requested one (upsert)
    all_configs = await db.scalars(select(AIProviderConfig))
    for cfg in all_configs:
        cfg.is_active = False

    target = await db.scalar(
        select(AIProviderConfig).where(
            AIProviderConfig.provider == body.provider,
            AIProviderConfig.model_id == body.model_id,
        )
    )
    if not target:
        target = AIProviderConfig(provider=body.provider, model_id=body.model_id)
        db.add(target)

    target.is_active = True
    await db.commit()
    await db.refresh(target)
    return target


# ---------------------------------------------------------------------------
# Topic management
# ---------------------------------------------------------------------------

@router.get("/topics", response_model=list[TopicOut])
async def list_topics(db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Topic).order_by(Topic.name))
    return list(rows)


@router.post("/topics/{topic_id}/approve", response_model=OKResponse)
async def approve_topic(topic_id: int, db: AsyncSession = Depends(get_db)):
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    topic.is_approved = True
    await db.commit()
    return OKResponse()


@router.delete("/topics/{topic_id}", response_model=OKResponse)
async def delete_topic(topic_id: int, db: AsyncSession = Depends(get_db)):
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    await db.delete(topic)
    await db.commit()
    return OKResponse()


# ---------------------------------------------------------------------------
# Unresolved topics (review queue)
# ---------------------------------------------------------------------------

@router.get("/unresolved-topics", response_model=list[UnresolvedTopicOut])
async def list_unresolved(db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(UnresolvedTopic).order_by(UnresolvedTopic.occurrence_count.desc())
    )
    return list(rows)


@router.post("/unresolved-topics/{unresolved_id}/resolve", response_model=OKResponse)
async def resolve_topic(
    unresolved_id: int,
    canonical_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Assign an unresolved topic string to an existing canonical topic."""
    unresolved = await db.get(UnresolvedTopic, unresolved_id)
    if not unresolved:
        raise HTTPException(status_code=404, detail="Unresolved topic not found")
    canonical = await db.get(Topic, canonical_id)
    if not canonical:
        raise HTTPException(status_code=404, detail="Canonical topic not found")

    # Add the raw_text as an alias on the canonical topic
    aliases = list(canonical.aliases or [])
    if unresolved.raw_text not in aliases:
        aliases.append(unresolved.raw_text)
        canonical.aliases = aliases

    await db.delete(unresolved)
    await db.commit()
    return OKResponse()


@router.post("/unresolved-topics/{unresolved_id}/create-new", response_model=TopicOut)
async def promote_to_topic(unresolved_id: int, db: AsyncSession = Depends(get_db)):
    """Promote an unresolved string into a new canonical topic."""
    from backend.topics.canonicalizer import TopicCanonicalizer
    unresolved = await db.get(UnresolvedTopic, unresolved_id)
    if not unresolved:
        raise HTTPException(status_code=404, detail="Unresolved topic not found")

    slug = unresolved.raw_text.lower().replace(" ", "-")
    topic = Topic(name=unresolved.raw_text, slug=slug, is_approved=True)
    db.add(topic)
    await db.delete(unresolved)
    await db.commit()
    await db.refresh(topic)
    return topic


# ---------------------------------------------------------------------------
# Pipeline / analysis triggers + live status
# ---------------------------------------------------------------------------

@router.get("/run/status", response_model=list[JobStatusOut])
async def get_job_statuses():
    """Return current status and logs for all three pipeline jobs."""
    return [
        JobStatusOut(
            job=name,
            status=_jobs[name]["status"],
            logs=_jobs[name]["logs"],
            started_at=_jobs[name]["started_at"],
            finished_at=_jobs[name]["finished_at"],
        )
        for name in _JOB_NAMES
    ]


@router.post("/run/pipeline", response_model=OKResponse)
async def trigger_pipeline(background_tasks: BackgroundTasks):
    """Process collected raw items through the full pipeline."""
    if _jobs["pipeline"]["status"] == "running":
        raise HTTPException(status_code=409, detail="Pipeline is already running.")

    async def _run():
        _start("pipeline")
        log = _make_logger("pipeline")
        try:
            from backend.processors.pipeline import run_pipeline
            await run_pipeline(log_fn=log)
            _finish("pipeline")
        except Exception as exc:
            _fail("pipeline", str(exc), traceback.format_exc())

    background_tasks.add_task(_run)
    return OKResponse()


@router.post("/run/analysis", response_model=OKResponse)
async def trigger_analysis(background_tasks: BackgroundTasks):
    """Run priority engine, trend snapshots, and all pattern detectors."""
    if _jobs["analysis"]["status"] == "running":
        raise HTTPException(status_code=409, detail="Analysis is already running.")

    async def _run():
        _start("analysis")
        log = _make_logger("analysis")
        try:
            from backend.analyzers.priority_engine import run_priority_engine
            from backend.analyzers.trend_detector import backfill_snapshots
            from backend.analyzers.emergence import detect_emerging
            from backend.analyzers.cross_source import detect_cross_source
            from backend.analyzers.hype_detector import detect_hype_peaks
            from backend.analyzers.content_gaps import detect_content_gaps

            await run_priority_engine(log_fn=log)

            log("Backfilling trend snapshots (last 30 days)...")
            await backfill_snapshots(days=30, log_fn=log)

            log("Detecting emerging topics...")
            e = await detect_emerging()
            log(f"  ↳ {e} emerging pattern(s) found.")

            log("Detecting cross-source correlations...")
            c = await detect_cross_source()
            log(f"  ↳ {c} cross-source pattern(s) found.")

            log("Detecting hype peaks...")
            h = await detect_hype_peaks()
            log(f"  ↳ {h} hype peak(s) detected.")

            log("Detecting content gaps...")
            g = await detect_content_gaps()
            log(f"  ↳ {g} content gap(s) identified.")

            log("Analysis complete.")
            _finish("analysis")
        except Exception as exc:
            _fail("analysis", str(exc), traceback.format_exc())

    background_tasks.add_task(_run)
    return OKResponse()


@router.post("/run/suggestions", response_model=OKResponse)
async def trigger_suggestions(background_tasks: BackgroundTasks):
    """Generate content suggestions from scored topics (uses LLM)."""
    if _jobs["suggestions"]["status"] == "running":
        raise HTTPException(status_code=409, detail="Suggestions job is already running.")

    async def _run():
        _start("suggestions")
        log = _make_logger("suggestions")
        try:
            from backend.analyzers.suggestion_generator import generate_suggestions
            await generate_suggestions(log_fn=log)
            _finish("suggestions")
        except Exception as exc:
            _fail("suggestions", str(exc), traceback.format_exc())

    background_tasks.add_task(_run)
    return OKResponse()


# ---------------------------------------------------------------------------
# RSS feed management
# ---------------------------------------------------------------------------

@router.get("/rss-feeds", response_model=list[RssFeedOut])
async def list_rss_feeds(db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(RssFeed).order_by(RssFeed.category, RssFeed.name))
    return list(rows)


@router.post("/rss-feeds", response_model=RssFeedOut, status_code=201)
async def create_rss_feed(body: RssFeedCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(RssFeed).where(RssFeed.url == body.url))
    if existing:
        raise HTTPException(status_code=409, detail="A feed with this URL already exists")
    feed = RssFeed(
        url=body.url,
        name=body.name,
        category=body.category,
        is_active=body.is_active,
    )
    db.add(feed)
    await db.commit()
    await db.refresh(feed)
    return feed


@router.put("/rss-feeds/{feed_id}", response_model=RssFeedOut)
async def update_rss_feed(feed_id: int, body: RssFeedUpdate, db: AsyncSession = Depends(get_db)):
    feed = await db.get(RssFeed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    if body.name is not None:
        feed.name = body.name
    if body.category is not None:
        feed.category = body.category
    if body.is_active is not None:
        feed.is_active = body.is_active
    await db.commit()
    await db.refresh(feed)
    return feed


@router.delete("/rss-feeds/{feed_id}", response_model=OKResponse)
async def delete_rss_feed(feed_id: int, db: AsyncSession = Depends(get_db)):
    feed = await db.get(RssFeed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    await db.delete(feed)
    await db.commit()
    return OKResponse()


@router.post("/rss-feeds/test", response_model=RssFeedTestResult)
async def test_rss_feed(body: RssFeedCreate):
    """Validate a feed URL and return a preview of its entries."""
    import asyncio
    import feedparser

    def _fetch():
        return feedparser.parse(body.url, request_headers={"User-Agent": "aionic/1.0"})

    loop = asyncio.get_event_loop()
    try:
        feed = await loop.run_in_executor(None, _fetch)
    except Exception as exc:
        return RssFeedTestResult(
            url=body.url, ok=False, title=None,
            entry_count=0, sample_titles=[], error=str(exc),
        )

    if feed.bozo and not feed.entries:
        return RssFeedTestResult(
            url=body.url, ok=False,
            title=getattr(feed.feed, "title", None),
            entry_count=0, sample_titles=[],
            error=str(feed.bozo_exception) if hasattr(feed, "bozo_exception") else "Feed parse error",
        )

    sample = [e.get("title", "(no title)") for e in feed.entries[:5]]
    return RssFeedTestResult(
        url=body.url,
        ok=True,
        title=getattr(feed.feed, "title", None),
        entry_count=len(feed.entries),
        sample_titles=sample,
        error=None,
    )


# ---------------------------------------------------------------------------
# Performance tracking
# ---------------------------------------------------------------------------

@router.post("/performance", response_model=OKResponse)
async def record_performance(body: PerformanceSubmit, db: AsyncSession = Depends(get_db)):
    record = ContentPerformance(
        suggestion_id=body.suggestion_id,
        article_title=body.article_title,
        published_at=body.published_at,
        views=body.views,
        engagement_score=body.engagement_score,
    )
    db.add(record)
    await db.commit()
    return OKResponse()
