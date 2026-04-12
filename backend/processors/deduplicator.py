"""
Content-level deduplicator using MinHash + LSH (datasketch).

Strategy:
  - Build a MinHash signature for each item from its title+content n-grams
  - Insert into an LSH index; query for near-duplicates before inserting
  - Threshold: 0.90 Jaccard similarity
  - When a duplicate is found, mark the newer item with duplicate_of_id

This is content-level dedup. Source-level dedup (source + source_id)
already happens in BaseCollector._upsert().
"""
import logging
from typing import Generator

from datasketch import MinHash, MinHashLSH
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models import RawItem
from backend.processors.normalizer import extract_text_for_hashing, tokenize_for_minhash

logger = logging.getLogger(__name__)

MINHASH_NUM_PERM = 128
JACCARD_THRESHOLD = 0.90


def _build_minhash(text: str) -> MinHash:
    m = MinHash(num_perm=MINHASH_NUM_PERM)
    for ngram in tokenize_for_minhash(text):
        m.update(ngram.encode("utf-8"))
    return m


class Deduplicator:
    """
    Stateful deduplicator. Build once per pipeline run, feed items through it.
    Not thread-safe — use a single instance per pipeline invocation.
    """

    def __init__(self):
        self._lsh = MinHashLSH(threshold=JACCARD_THRESHOLD, num_perm=MINHASH_NUM_PERM)
        self._id_to_minhash: dict[int, MinHash] = {}

    def add(self, item_id: int, text: str) -> int | None:
        """
        Add an item to the index.
        Returns the ID of the first near-duplicate found, or None if unique.
        """
        if not text.strip():
            return None

        mh = _build_minhash(text)
        candidates = self._lsh.query(mh)

        if candidates:
            # Return the first (oldest by insertion order) duplicate
            return int(candidates[0])

        # Unique — insert
        try:
            self._lsh.insert(str(item_id), mh)
            self._id_to_minhash[item_id] = mh
        except ValueError:
            # Already inserted (shouldn't happen, but safe to ignore)
            pass

        return None


async def deduplicate_batch(
    items: list[RawItem],
    session: AsyncSession,
) -> dict[int, int | None]:
    """
    Deduplicate a batch of RawItems.
    Returns {item_id: duplicate_of_id | None}.
    Updates duplicate_of_id on the DB records in-place.
    """
    dedup = Deduplicator()
    result: dict[int, int | None] = {}

    for item in items:
        text = extract_text_for_hashing(item.title, item.content)
        dup_of = dedup.add(item.id, text)
        result[item.id] = dup_of

        if dup_of is not None:
            item.duplicate_of_id = dup_of
            logger.debug("Item %d is near-duplicate of %d", item.id, dup_of)

    await session.commit()
    return result


async def deduplicate_against_existing(
    new_items: list[RawItem],
    session: AsyncSession,
    lookback_limit: int = 5000,
) -> dict[int, int | None]:
    """
    Deduplicate new_items against the most recent existing processed items.
    Loads recent items into the LSH index first, then checks new_items.
    """
    dedup = Deduplicator()

    # Seed LSH with recent existing items (already processed)
    existing = await session.scalars(
        select(RawItem)
        .where(
            RawItem.processed == True,  # noqa: E712
            RawItem.duplicate_of_id.is_(None),
        )
        .order_by(RawItem.collected_at.desc())
        .limit(lookback_limit)
    )
    for item in existing:
        text = extract_text_for_hashing(item.title, item.content)
        if text.strip():
            try:
                mh = _build_minhash(text)
                dedup._lsh.insert(str(item.id), mh)
                dedup._id_to_minhash[item.id] = mh
            except ValueError:
                pass

    # Now check new items
    result: dict[int, int | None] = {}
    for item in new_items:
        text = extract_text_for_hashing(item.title, item.content)
        dup_of = dedup.add(item.id, text)
        result[item.id] = dup_of
        if dup_of is not None:
            item.duplicate_of_id = dup_of

    await session.commit()
    return result
