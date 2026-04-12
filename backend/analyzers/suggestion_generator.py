"""
Content suggestion generator.

Takes the top-scored topics from topic_scores and generates
editorial content ideas using the LLM.

Architecture principle: LLM explains pre-computed scores — it does NOT
decide what's important. The scoring is already done by priority_engine.py.

The LLM's job here:
  - Given a topic, its score breakdown, and recent context (summaries)
  - Generate specific, compelling article title ideas
  - Provide editorial rationale
  - Surface unique insights from the data

Results cached in llm_cache by default (7-day TTL).
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from backend.db.database import AsyncSessionLocal
from backend.db.models import (
    Topic, TopicScore, ContentSuggestion, ProcessedItem, TopicMention, RawItem
)
from backend.ai import provider as ai

logger = logging.getLogger(__name__)

MAX_TOPICS_PER_RUN = 10
MIN_SCORE_FOR_SUGGESTION = 0.45
SUGGESTION_COOLDOWN_DAYS = 14  # don't suggest the same topic twice within N days

SYSTEM_PROMPT = (
    "You are an editorial strategist for an AI trends publication. "
    "You receive trending topic data with deterministic scores and suggest compelling article ideas. "
    "Be specific and actionable. Respond ONLY with valid JSON."
)

PROMPT_TEMPLATE = """\
This AI topic is trending in our data. Generate content ideas.

Topic: {topic_name}
Category: {category}
Score: {score:.2f} / 1.00 ({classification})
Confidence: {confidence}
Sources covering it: {source_count} sources over {consistency_days} days
Score breakdown: {breakdown}

Recent summaries from collected content:
{context_snippets}

Return JSON:
{{
  "article_titles": ["Title 1", "Title 2", "Title 3"],
  "rationale": "Why this topic deserves coverage now (2-3 sentences)",
  "insight": "The most surprising or non-obvious finding from the data (1-2 sentences)",
  "urgency_note": "Why NOW specifically (timing signal)"
}}
"""


async def generate_suggestions(
    session: AsyncSession | None = None,
    log_fn=None,
) -> int:
    """
    Generate content suggestions for the top-scored topics.
    Returns count of new suggestions written.
    """
    if session is None:
        async with AsyncSessionLocal() as _session:
            return await generate_suggestions(_session, log_fn)

    def _log(msg: str):
        logger.info(msg)
        if log_fn:
            log_fn(msg)

    now = datetime.now(timezone.utc)
    cooldown_cutoff = now - timedelta(days=SUGGESTION_COOLDOWN_DAYS)

    _log(f"Loading top-scored topics (minimum score {MIN_SCORE_FOR_SUGGESTION})...")
    # Get latest scores
    subq = (
        select(
            TopicScore.topic_id,
            func.max(TopicScore.computed_at).label("max_at"),
        )
        .group_by(TopicScore.topic_id)
        .subquery()
    )
    rows = list(await session.execute(
        select(TopicScore, Topic)
        .join(subq, (TopicScore.topic_id == subq.c.topic_id) &
              (TopicScore.computed_at == subq.c.max_at))
        .join(Topic, TopicScore.topic_id == Topic.id)
        .where(TopicScore.score >= MIN_SCORE_FOR_SUGGESTION)
        .order_by(desc(TopicScore.score))
        .limit(MAX_TOPICS_PER_RUN * 2)  # fetch extra to account for cooldown skips
    ))

    eligible = [r for r in rows]
    _log(f"Found {len(eligible)} eligible topics. Processing up to {MAX_TOPICS_PER_RUN}.")
    written = 0

    for ts, topic in eligible:
        if written >= MAX_TOPICS_PER_RUN:
            break

        # Skip if suggested recently
        recent = await session.scalar(
            select(ContentSuggestion).where(
                ContentSuggestion.created_at >= cooldown_cutoff,
                func.array_position(ContentSuggestion.topic_ids, topic.id).isnot(None),
            )
        )
        if recent:
            continue

        # Compute a hash of the score to enable LLM cache invalidation when score changes
        score_hash = hashlib.md5(
            f"{topic.id}:{ts.score:.4f}:{ts.classification}".encode()
        ).hexdigest()[:16]

        # Check if we already have a suggestion with this exact score hash (LLM cache)
        cached = await session.scalar(
            select(ContentSuggestion).where(
                ContentSuggestion.score_hash == score_hash,
                func.array_position(ContentSuggestion.topic_ids, topic.id).isnot(None),
            )
        )
        if cached:
            continue

        # Gather context: recent summaries for this topic
        context_snippets = await _gather_context(topic.id, session)

        prompt = PROMPT_TEMPLATE.format(
            topic_name=topic.name,
            category=topic.category or "general",
            score=ts.score,
            classification=ts.classification.replace("_", " "),
            confidence=ts.confidence_level,
            source_count=ts.source_count,
            consistency_days=ts.consistency_days,
            breakdown=json.dumps(ts.score_breakdown or {}, indent=2),
            context_snippets=context_snippets,
        )

        _log(f"Generating suggestion for '{topic.name}' (score: {ts.score:.2f}, {ts.classification.replace('_', ' ')})...")
        result = await ai.complete(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            session=session,
            use_cache=True,
        )

        parsed = _parse_result(result)
        if not parsed:
            _log(f"  ↳ LLM response could not be parsed, skipping.")
            continue

        suggestion = ContentSuggestion(
            title=parsed["article_titles"][0] if parsed["article_titles"] else f"Article about {topic.name}",
            rationale=parsed.get("rationale"),
            insight=parsed.get("insight"),
            suggested_articles=parsed.get("article_titles", []),
            topic_ids=[topic.id],
            topic_score_id=ts.id,
            urgency_score=ts.score,
            confidence_level=ts.confidence_level,
            score_hash=score_hash,
            created_at=now,
        )
        session.add(suggestion)
        written += 1

    await session.commit()
    _log(f"Done — {written} suggestion{'s' if written != 1 else ''} generated.")
    return written


async def _gather_context(topic_id: int, session: AsyncSession) -> str:
    """Gather up to 5 recent summaries for this topic as context."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    # Get raw_item_ids that mention this topic
    mention_item_ids = await session.scalars(
        select(TopicMention.raw_item_id).where(
            TopicMention.topic_id == topic_id,
            TopicMention.mentioned_at >= cutoff,
        ).limit(20)
    )
    item_ids = list(mention_item_ids)
    if not item_ids:
        return "No recent context available."

    # Get ProcessedItem summaries
    processed = await session.scalars(
        select(ProcessedItem).where(
            ProcessedItem.raw_item_id.in_(item_ids),
            ProcessedItem.summary.is_not(None),
        ).limit(5)
    )
    snippets = []
    for pi in processed:
        if pi.summary:
            snippets.append(f"- {pi.summary[:200]}")

    if not snippets:
        # Fall back to raw titles
        raw_items = await session.scalars(
            select(RawItem).where(
                RawItem.id.in_(item_ids[:5]),
                RawItem.title.is_not(None),
            )
        )
        snippets = [f"- {r.title}" for r in raw_items if r.title]

    return "\n".join(snippets) if snippets else "No recent context available."


def _parse_result(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return None

    titles = [str(t) for t in (data.get("article_titles") or [])[:5]]
    if not titles:
        return None
    return {
        "article_titles": titles,
        "rationale": str(data.get("rationale", ""))[:1000],
        "insight": str(data.get("insight", ""))[:500],
        "urgency_note": str(data.get("urgency_note", ""))[:300],
    }
