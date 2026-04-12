from datetime import datetime, date
from sqlalchemy import (
    String, Text, Float, Boolean, Integer, DateTime, Date,
    ForeignKey, JSON, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db.database import Base


# ---------------------------------------------------------------------------
# Raw collected items
# ---------------------------------------------------------------------------

class RawItem(Base):
    __tablename__ = "raw_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(256))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_metadata: Mapped[dict | None] = mapped_column(JSON)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    importance_score: Mapped[float | None] = mapped_column(Float)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("raw_items.id"))
    mention_count: Mapped[int] = mapped_column(Integer, default=1)

    processed_item: Mapped["ProcessedItem | None"] = relationship(
        back_populates="raw_item", uselist=False
    )
    topic_mentions: Mapped[list["TopicMention"]] = relationship(back_populates="raw_item")

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_raw_items_source_id"),
        Index("ix_raw_items_published_at", "published_at"),
        Index("ix_raw_items_processed_importance", "processed", "importance_score"),
    )


# ---------------------------------------------------------------------------
# Processed / enriched items
# ---------------------------------------------------------------------------

class ProcessedItem(Base):
    __tablename__ = "processed_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_item_id: Mapped[int] = mapped_column(
        ForeignKey("raw_items.id", ondelete="CASCADE"), unique=True
    )
    summary: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(50), index=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    ai_topics: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    importance_score: Mapped[float | None] = mapped_column(Float)
    llm_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    raw_item: Mapped["RawItem"] = relationship(back_populates="processed_item")


# ---------------------------------------------------------------------------
# Canonical topics
# ---------------------------------------------------------------------------

class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    category: Mapped[str | None] = mapped_column(String(50))
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    mentions: Mapped[list["TopicMention"]] = relationship(back_populates="topic")
    snapshots: Mapped[list["TrendSnapshot"]] = relationship(back_populates="topic")
    scores: Mapped[list["TopicScore"]] = relationship(back_populates="topic")


# ---------------------------------------------------------------------------
# Unresolved topic strings (admin review queue)
# ---------------------------------------------------------------------------

class UnresolvedTopic(Base):
    __tablename__ = "unresolved_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_text: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    suggested_canonical_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"))
    suggested_merge_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# Topic mentions (occurrence tracking per source)
# ---------------------------------------------------------------------------

class TopicMention(Base):
    __tablename__ = "topic_mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    raw_item_id: Mapped[int] = mapped_column(
        ForeignKey("raw_items.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(50), index=True)
    mentioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    topic: Mapped["Topic"] = relationship(back_populates="mentions")
    raw_item: Mapped["RawItem"] = relationship(back_populates="topic_mentions")

    __table_args__ = (
        UniqueConstraint("topic_id", "raw_item_id", name="uq_topic_mention"),
    )


# ---------------------------------------------------------------------------
# Daily trend snapshots
# ---------------------------------------------------------------------------

class TrendSnapshot(Base):
    __tablename__ = "trend_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    weighted_mention_count: Mapped[float] = mapped_column(Float, default=0.0)
    sources: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    momentum_score: Mapped[float | None] = mapped_column(Float)
    sentiment_avg: Mapped[float | None] = mapped_column(Float)

    topic: Mapped["Topic"] = relationship(back_populates="snapshots")

    __table_args__ = (
        UniqueConstraint("topic_id", "snapshot_date", name="uq_trend_snapshot"),
    )


# ---------------------------------------------------------------------------
# Detected patterns
# ---------------------------------------------------------------------------

class Pattern(Base):
    __tablename__ = "patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern_type: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict | None] = mapped_column(JSON)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    topic_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))


# ---------------------------------------------------------------------------
# Central priority engine scores
# ---------------------------------------------------------------------------

class TopicScore(Base):
    __tablename__ = "topic_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    score: Mapped[float] = mapped_column(Float, default=0.0)
    classification: Mapped[str] = mapped_column(
        String(20), default="ignore"
    )  # write_now | monitor | ignore
    score_breakdown: Mapped[dict | None] = mapped_column(JSON)
    confidence_level: Mapped[str] = mapped_column(String(10), default="low")  # high | medium | low
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    consistency_days: Mapped[int] = mapped_column(Integer, default=0)

    topic: Mapped["Topic"] = relationship(back_populates="scores")


# ---------------------------------------------------------------------------
# Content suggestions (LLM explains pre-computed scores)
# ---------------------------------------------------------------------------

class ContentSuggestion(Base):
    __tablename__ = "content_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512))
    rationale: Mapped[str | None] = mapped_column(Text)
    insight: Mapped[str | None] = mapped_column(Text)
    suggested_articles: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    topic_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    topic_score_id: Mapped[int | None] = mapped_column(ForeignKey("topic_scores.id"))
    urgency_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_level: Mapped[str] = mapped_column(String(10), default="low")
    score_hash: Mapped[str | None] = mapped_column(String(64))  # for LLM output caching
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    used: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------------------
# Feedback loop: article performance
# ---------------------------------------------------------------------------

class ContentPerformance(Base):
    __tablename__ = "content_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suggestion_id: Mapped[int | None] = mapped_column(ForeignKey("content_suggestions.id"))
    article_title: Mapped[str] = mapped_column(String(512))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    views: Mapped[int | None] = mapped_column(Integer)
    engagement_score: Mapped[float | None] = mapped_column(Float)
    signal_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# Admin-editable source weights
# ---------------------------------------------------------------------------

class SourceWeight(Base):
    __tablename__ = "source_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    updated_by: Mapped[str | None] = mapped_column(String(100))

    history: Mapped[list["SourceWeightHistory"]] = relationship(
        back_populates="source_weight"
    )


class SourceWeightHistory(Base):
    __tablename__ = "source_weight_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_weight_id: Mapped[int] = mapped_column(ForeignKey("source_weights.id"))
    old_weight: Mapped[float] = mapped_column(Float)
    new_weight: Mapped[float] = mapped_column(Float)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    source_weight: Mapped["SourceWeight"] = relationship(back_populates="history")


# ---------------------------------------------------------------------------
# LLM response cache
# ---------------------------------------------------------------------------

class LLMCache(Base):
    __tablename__ = "llm_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prompt_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


# ---------------------------------------------------------------------------
# AI provider config
# ---------------------------------------------------------------------------

class AIProviderConfig(Base):
    __tablename__ = "ai_provider_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# Dynamic RSS feed registry
# ---------------------------------------------------------------------------

class RssFeed(Base):
    __tablename__ = "rss_feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="general")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# Admin-managed system configuration (replaces .env for app secrets/settings)
# ---------------------------------------------------------------------------

class SystemConfig(Base):
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(50), default="general")
    description: Mapped[str | None] = mapped_column(String(256))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
