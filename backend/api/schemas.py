from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class OKResponse(BaseModel):
    status: str = "ok"


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    category: str | None
    aliases: list[str] | None
    is_approved: bool


class UnresolvedTopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    raw_text: str
    occurrence_count: int
    suggested_canonical_id: int | None
    suggested_merge_id: int | None
    first_seen_at: datetime
    last_seen_at: datetime


# ---------------------------------------------------------------------------
# Raw sources
# ---------------------------------------------------------------------------

class RawItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: str
    url: str | None
    title: str | None
    author: str | None
    published_at: datetime | None
    collected_at: datetime
    category: str | None = None
    importance_score: float | None
    mention_count: int


# ---------------------------------------------------------------------------
# Trend data
# ---------------------------------------------------------------------------

class TopicItemOut(BaseModel):
    id: int
    source: str
    title: str | None
    url: str | None
    author: str | None
    published_at: datetime | None
    importance_score: float | None


class TopicSourceBreakdown(BaseModel):
    source: str
    mention_count: int

class TrendingTopicOut(BaseModel):
    topic_id: int
    name: str
    slug: str
    category: str | None
    score: float
    classification: str
    confidence_level: str
    source_count: int
    consistency_days: int
    score_breakdown: dict | None


class TimeSeriesPoint(BaseModel):
    snapshot_date: date
    mention_count: int
    weighted_mention_count: float
    momentum_score: float | None
    sentiment_avg: float | None
    sources: list[str] | None


class TopicTimeSeriesOut(BaseModel):
    topic_id: int
    name: str
    slug: str
    data: list[TimeSeriesPoint]


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

class PatternOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pattern_type: str
    title: str
    description: str | None
    evidence: dict | None
    confidence_score: float
    detected_at: datetime
    topic_ids: list[int] | None


# ---------------------------------------------------------------------------
# Content suggestions
# ---------------------------------------------------------------------------

class ContentSuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    rationale: str | None
    insight: str | None
    suggested_articles: list[str] | None
    topic_ids: list[int] | None
    urgency_score: float
    confidence_level: str
    created_at: datetime
    used: bool


# ---------------------------------------------------------------------------
# Admin — RSS feed management
# ---------------------------------------------------------------------------

class RssFeedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    url: str
    name: str
    category: str
    is_active: bool
    last_collected_at: datetime | None
    last_error: str | None
    error_count: int
    item_count: int
    created_at: datetime
    updated_at: datetime


class RssFeedCreate(BaseModel):
    url: str
    name: str
    category: str = "general"
    is_active: bool = True


class RssFeedUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    is_active: bool | None = None


class RssFeedTestResult(BaseModel):
    url: str
    ok: bool
    title: str | None
    entry_count: int
    sample_titles: list[str]
    error: str | None


# ---------------------------------------------------------------------------
# Admin — source weights
# ---------------------------------------------------------------------------

class SourceWeightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: str
    weight: float
    updated_at: datetime


class SourceWeightUpdate(BaseModel):
    weight: float


# ---------------------------------------------------------------------------
# Admin — AI provider
# ---------------------------------------------------------------------------

class AIProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    provider: str
    model_id: str
    is_active: bool
    updated_at: datetime


class AIProviderUpdate(BaseModel):
    provider: str
    model_id: str


# ---------------------------------------------------------------------------
# Admin — system config
# ---------------------------------------------------------------------------

class SystemConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    value: str          # secrets are masked by the endpoint, not here
    is_secret: bool
    category: str
    description: str | None
    updated_at: datetime


class SystemConfigUpdate(BaseModel):
    value: str


# ---------------------------------------------------------------------------
# Admin — job run status
# ---------------------------------------------------------------------------

class JobLogEntry(BaseModel):
    t: str
    msg: str


class LogEntryOut(BaseModel):
    t: str
    level: str
    logger: str
    msg: str


class JobStatusOut(BaseModel):
    job: str
    status: str   # idle | running | done | error
    logs: list[JobLogEntry]
    started_at: str | None
    finished_at: str | None


# ---------------------------------------------------------------------------
# Admin — performance tracking
# ---------------------------------------------------------------------------

class PerformanceSubmit(BaseModel):
    suggestion_id: int | None = None
    article_title: str
    published_at: datetime | None = None
    views: int | None = None
    engagement_score: float | None = None


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class SystemStats(BaseModel):
    total_items: int
    items_today: int
    items_last_7d: int
    total_topics: int
    active_topics: int
    patterns_detected: int
    suggestions_available: int
    sources_active: list[str]
    last_collection_at: datetime | None
