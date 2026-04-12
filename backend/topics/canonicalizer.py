"""
Topic canonicalizer: resolves any raw topic string to a canonical Topic.
No raw topic string may enter topic_mentions without passing through resolve().
"""
import re
import logging
from functools import lru_cache
from datetime import datetime, timezone

from rapidfuzz import fuzz
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.db.models import Topic, UnresolvedTopic

logger = logging.getLogger(__name__)

# Minimum fuzzy score (0–100) to accept a match
FUZZY_THRESHOLD = 85
# How many occurrences before an unresolved string is surfaced for admin review
REVIEW_THRESHOLD = 5

# Common abbreviation expansions
EXPANSIONS: dict[str, str] = {
    "llm": "large language model",
    "llms": "large language models",
    "rag": "retrieval augmented generation",
    "rlhf": "reinforcement learning from human feedback",
    "moe": "mixture of experts",
    "vlm": "vision language model",
    "asr": "automatic speech recognition",
    "tts": "text to speech",
    "mlops": "machine learning operations",
    "xai": "explainable ai",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "gan": "generative adversarial network",
    "vae": "variational autoencoder",
    "gpt": "generative pre-trained transformer",
}


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Expand known abbreviations (whole-word only)
    words = text.split()
    words = [EXPANSIONS.get(w, w) for w in words]
    return " ".join(words)


class TopicCanonicalizer:
    """
    Thread-safe canonical topic resolver.
    Cache is per-instance — create one instance and reuse it.
    """

    def __init__(self):
        # slug → Topic mapping, loaded lazily
        self._cache: dict[str, Topic] = {}
        self._initialized = False

    async def load(self, session: AsyncSession) -> None:
        """Load all approved topics into memory."""
        rows = await session.scalars(select(Topic).where(Topic.is_approved == True))
        topics = list(rows)
        self._cache = {}
        for topic in topics:
            self._cache[topic.slug] = topic
            # Index all aliases
            for alias in (topic.aliases or []):
                norm = normalize(alias)
                self._cache[norm] = topic
            # Index normalized name
            self._cache[normalize(topic.name)] = topic
        self._initialized = True

    async def resolve(self, raw_text: str, session: AsyncSession) -> Topic | None:
        """
        Resolve raw_text to a canonical Topic.
        Returns None if unresolvable (caller should decide whether to skip or flag).
        """
        if not self._initialized:
            await self.load(session)

        norm = normalize(raw_text)
        if not norm:
            return None

        # 1. Exact match
        if norm in self._cache:
            return self._cache[norm]

        # 2. Fuzzy match against all keys
        best_score = 0
        best_topic: Topic | None = None
        for key, topic in self._cache.items():
            score = fuzz.token_sort_ratio(norm, key)
            if score > best_score:
                best_score = score
                best_topic = topic

        if best_score >= FUZZY_THRESHOLD and best_topic:
            # Cache this mapping to skip future fuzzy search
            self._cache[norm] = best_topic
            return best_topic

        # 3. No match — track in unresolved queue
        await self._track_unresolved(raw_text, norm, session)
        return None

    async def _track_unresolved(
        self, raw_text: str, norm: str, session: AsyncSession
    ) -> None:
        existing = await session.scalar(
            select(UnresolvedTopic).where(UnresolvedTopic.raw_text == norm)
        )
        if existing:
            existing.occurrence_count += 1
            existing.last_seen_at = datetime.now(timezone.utc)
        else:
            session.add(UnresolvedTopic(raw_text=norm))

        await session.commit()

        # Find auto-merge candidates if this is newly frequent
        if existing and existing.occurrence_count == REVIEW_THRESHOLD:
            await self._suggest_merge(existing, session)

    async def _suggest_merge(
        self, unresolved: UnresolvedTopic, session: AsyncSession
    ) -> None:
        """
        When an unresolved string hits the review threshold,
        find the closest canonical topic and store it as a suggestion.
        """
        norm = unresolved.raw_text
        best_score = 0
        best_topic_id: int | None = None

        rows = await session.scalars(select(Topic).where(Topic.is_approved == True))
        for topic in rows:
            score = fuzz.token_sort_ratio(norm, normalize(topic.name))
            if score > best_score:
                best_score = score
                best_topic_id = topic.id

        if best_score >= 70 and best_topic_id:
            await session.execute(
                update(UnresolvedTopic)
                .where(UnresolvedTopic.id == unresolved.id)
                .values(suggested_merge_id=best_topic_id)
            )
            await session.commit()

    async def invalidate(self) -> None:
        """Force cache reload on next resolve call."""
        self._cache = {}
        self._initialized = False

    async def approve_unresolved(
        self, unresolved_id: int, canonical_topic_id: int, session: AsyncSession
    ) -> None:
        """Admin action: map an unresolved string to a canonical topic."""
        unresolved = await session.get(UnresolvedTopic, unresolved_id)
        if not unresolved:
            return
        topic = await session.get(Topic, canonical_topic_id)
        if not topic:
            return
        # Add as alias
        aliases = list(topic.aliases or [])
        if unresolved.raw_text not in aliases:
            aliases.append(unresolved.raw_text)
            topic.aliases = aliases
        await session.delete(unresolved)
        await session.commit()
        await self.invalidate()


# Module-level singleton
_canonicalizer: TopicCanonicalizer | None = None


def get_canonicalizer() -> TopicCanonicalizer:
    global _canonicalizer
    if _canonicalizer is None:
        _canonicalizer = TopicCanonicalizer()
    return _canonicalizer
