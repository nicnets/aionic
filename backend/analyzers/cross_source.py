"""
Cross-source correlation analyzer.

Finds topic pairs (and clusters) that consistently co-occur across
multiple sources — a signal that they represent a convergent narrative.

Strategy:
  - For each pair of topics, compute co-occurrence count:
    number of RawItems in which both topics are mentioned
  - Pairs with co-occurrence >= MIN_CO_OCCUR and >= MIN_SOURCES get a pattern
  - Clusters are groups of 3+ related topics

Written to patterns table with type="cross_source_correlation".
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.database import AsyncSessionLocal
from backend.db.models import Topic, TopicMention, Pattern

logger = logging.getLogger(__name__)

MIN_CO_OCCUR = 5       # minimum co-occurrences in a raw_item
MIN_SOURCES = 2        # must appear together in at least 2 sources
MIN_CLUSTER_SIZE = 3   # minimum topics to form a cluster pattern


async def detect_cross_source(
    days: int = 14,
    session: AsyncSession | None = None,
) -> int:
    """
    Detect cross-source topic correlations.
    Returns count of patterns written.
    """
    if session is None:
        async with AsyncSessionLocal() as _session:
            return await detect_cross_source(days, _session)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # Load all mentions in the window: {raw_item_id: [(topic_id, source), ...]}
    mentions = list(await session.scalars(
        select(TopicMention).where(TopicMention.mentioned_at >= cutoff)
    ))

    item_topics: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for m in mentions:
        item_topics[m.raw_item_id].append((m.topic_id, m.source))

    # Build co-occurrence matrix: {(tid_a, tid_b): {sources}}
    co_occur: dict[tuple[int, int], set[str]] = defaultdict(set)

    for raw_item_id, topic_list in item_topics.items():
        if len(topic_list) < 2:
            continue
        topic_ids = [t[0] for t in topic_list]
        sources = {t[1] for t in topic_list}
        for a, b in combinations(sorted(set(topic_ids)), 2):
            co_occur[(a, b)].update(sources)

    # Filter to significant pairs
    strong_pairs = [
        (pair, srcs)
        for pair, srcs in co_occur.items()
        if len(srcs) >= MIN_SOURCES
    ]

    if not strong_pairs:
        return 0

    # Count raw co-occurrences per pair
    pair_counts: dict[tuple[int, int], int] = defaultdict(int)
    for _, topic_list in item_topics.items():
        topic_ids = sorted(set(t[0] for t in topic_list))
        for a, b in combinations(topic_ids, 2):
            pair_counts[(a, b)] += 1

    # Filter by MIN_CO_OCCUR
    strong_pairs = [
        (pair, srcs)
        for pair, srcs in strong_pairs
        if pair_counts[pair] >= MIN_CO_OCCUR
    ]

    # Load topic names
    topic_ids_needed = set()
    for (a, b), _ in strong_pairs:
        topic_ids_needed.add(a)
        topic_ids_needed.add(b)

    topic_map: dict[int, Topic] = {}
    if topic_ids_needed:
        rows = await session.scalars(
            select(Topic).where(Topic.id.in_(topic_ids_needed))
        )
        for t in rows:
            topic_map[t.id] = t

    # Build clusters: topics that form a highly-connected subgraph
    adjacency: dict[int, set[int]] = defaultdict(set)
    for (a, b), _ in strong_pairs:
        adjacency[a].add(b)
        adjacency[b].add(a)

    # Find cliques (simple greedy: start from most-connected nodes)
    written = 0
    written_pairs: set[frozenset] = set()

    # Write individual strong pair patterns
    for (a, b), sources in sorted(strong_pairs, key=lambda x: -pair_counts[x[0]])[:20]:
        pair_key = frozenset([a, b])
        if pair_key in written_pairs:
            continue
        written_pairs.add(pair_key)

        ta = topic_map.get(a)
        tb = topic_map.get(b)
        if not ta or not tb:
            continue

        count = pair_counts[(a, b)]
        confidence = min(count / 20.0, 1.0)  # 20+ co-occurrences = max confidence

        pattern = Pattern(
            pattern_type="cross_source_correlation",
            title=f"Correlated: {ta.name} + {tb.name}",
            description=(
                f"'{ta.name}' and '{tb.name}' co-occur in {count} items "
                f"across {len(sources)} sources, suggesting a convergent narrative."
            ),
            evidence={
                "topic_a": ta.name,
                "topic_b": tb.name,
                "co_occurrence_count": count,
                "sources": list(sources),
            },
            confidence_score=round(confidence, 3),
            detected_at=now,
            topic_ids=[a, b],
        )
        session.add(pattern)
        written += 1

    # Write cluster patterns (groups of 3+)
    cluster_nodes = {n for n, nbrs in adjacency.items() if len(nbrs) >= MIN_CLUSTER_SIZE - 1}
    if len(cluster_nodes) >= MIN_CLUSTER_SIZE:
        cluster_ids = sorted(cluster_nodes)[:10]  # cap
        cluster_topics = [topic_map[tid] for tid in cluster_ids if tid in topic_map]
        if len(cluster_topics) >= MIN_CLUSTER_SIZE:
            pattern = Pattern(
                pattern_type="topic_cluster",
                title=f"Topic cluster: {', '.join(t.name for t in cluster_topics[:4])}{'...' if len(cluster_topics) > 4 else ''}",
                description=(
                    f"A cluster of {len(cluster_topics)} related AI topics are converging "
                    f"across multiple sources over the last {days} days."
                ),
                evidence={
                    "topics": [t.name for t in cluster_topics],
                    "topic_ids": [t.id for t in cluster_topics],
                    "days": days,
                },
                confidence_score=0.75,
                detected_at=now,
                topic_ids=[t.id for t in cluster_topics],
            )
            session.add(pattern)
            written += 1

    await session.commit()
    logger.info("Cross-source analyzer: wrote %d patterns", written)
    return written
