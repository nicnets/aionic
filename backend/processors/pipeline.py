"""
Processing pipeline orchestrator.

Stages per batch of unprocessed RawItems:
  1. Normalize — clean title + content in-memory
  2. Score importance — deterministic, all items
  3. Deduplicate — MinHash against recent items
  4. Enrich (LLM) — only items >= importance threshold AND not duplicates
  5. Tag — extract + canonicalize topics (rule-based + LLM topics)
  6. Categorize — rule-based + LLM hint
  7. Persist — write ProcessedItem records, mark RawItems as processed
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.system_config import get_config
from backend.db.database import AsyncSessionLocal
from backend.db.models import RawItem, ProcessedItem
from backend.processors.normalizer import clean_title, clean_text
from backend.processors.importance_scorer import score_batch, is_llm_eligible
from backend.processors.deduplicator import deduplicate_against_existing
from backend.processors.summarizer import enrich_batch
from backend.processors.tagger import tag_item
from backend.processors.categorizer import categorize

logger = logging.getLogger(__name__)


async def run_pipeline(
    batch_size: int | None = None,
    log_fn=None,
) -> int:
    """
    Process one batch of unprocessed RawItems through the full pipeline.
    Returns count of successfully processed items.
    """
    def _log(msg: str):
        logger.info(msg)
        if log_fn:
            log_fn(msg)

    async with AsyncSessionLocal() as session:
        if batch_size is None:
            batch_size = int(await get_config(session, "processing_batch_size", "500"))
        _log(f"Batch size: {batch_size} items per run.")
        return await _process_batch(session, batch_size, _log)


async def _process_batch(session: AsyncSession, limit: int, _log=None) -> int:
    if _log is None:
        def _log(msg): logger.info(msg)

    # --- Stage 1: Fetch unprocessed items ---
    _log("Fetching unprocessed items from database...")
    items = list(
        await session.scalars(
            select(RawItem)
            .where(RawItem.processed == False)  # noqa: E712
            .order_by(RawItem.collected_at.asc())
            .limit(limit)
        )
    )

    if not items:
        _log("No unprocessed items found. Pipeline complete.")
        return 0

    _log(f"Found {len(items)} items to process.")

    # --- Stage 1b: Normalize ---
    _log("Normalizing titles and content...")
    for item in items:
        item.title = clean_title(item.title)
        item.content = clean_text(item.content)

    # --- Stage 2: Score importance ---
    _log("Scoring item importance (deterministic)...")
    scores = await score_batch(items, session)
    for item in items:
        item.importance_score = scores.get(item.id, 0.5)

    # --- Stage 3: Deduplicate ---
    _log("Deduplicating against existing items (MinHash)...")
    dup_map = await deduplicate_against_existing(items, session)
    unique_items = [i for i in items if not dup_map.get(i.id)]
    dup_items = [i for i in items if dup_map.get(i.id)]
    _log(f"Deduplication result: {len(unique_items)} unique, {len(dup_items)} duplicates.")

    # --- Stage 4: LLM enrichment ---
    eligibility = {
        i.id: await is_llm_eligible(i.importance_score or 0, session)
        for i in unique_items
    }
    llm_items = [i for i in unique_items if eligibility[i.id]]
    non_llm_items = [i for i in unique_items if not eligibility[i.id]]
    _log(f"Importance split: {len(llm_items)} items queued for LLM, {len(non_llm_items)} rule-only.")

    enrichments: dict[int, dict | None] = {}
    if llm_items:
        _log(f"Sending {len(llm_items)} items to LLM for enrichment (summaries, topics, sentiment)...")
        enrichments = await enrich_batch(llm_items, session)
        _log(f"LLM enrichment complete — {len(enrichments)} responses received.")
    else:
        _log("No items meet LLM threshold — skipping enrichment.")

    # --- Stages 5+6+7: Tag, categorize, persist ---
    _log("Tagging topics and categorizing items...")
    processed_count = 0

    for item in unique_items:
        enrich = enrichments.get(item.id)
        llm_topics = enrich.get("topics", []) if enrich else []
        llm_category = enrich.get("category") if enrich else None
        summary = enrich.get("summary") if enrich else None
        sentiment = enrich.get("sentiment") if enrich else None

        try:
            matched_topics = await tag_item(item, session, extra_topic_strings=llm_topics)
        except Exception:
            logger.exception("Tagging failed for item %d", item.id)
            matched_topics = []

        category = categorize(item, llm_category=llm_category)

        pi = ProcessedItem(
            raw_item_id=item.id,
            summary=summary,
            category=category,
            sentiment_score=sentiment,
            ai_topics=[t.name for t in matched_topics] if matched_topics else None,
            keywords=None,
            importance_score=item.importance_score,
            llm_processed=enrich is not None,
            processed_at=datetime.now(timezone.utc),
        )
        session.add(pi)
        item.processed = True
        processed_count += 1

    for item in dup_items:
        item.processed = True
        processed_count += 1

    _log("Saving results to database...")
    await session.commit()
    _log(f"Pipeline complete — {processed_count} items processed ({len(dup_items)} duplicates marked).")
    return processed_count


async def process_single(item_id: int) -> bool:
    """Process a single RawItem by ID. Useful for manual re-processing."""
    async with AsyncSessionLocal() as session:
        item = await session.get(RawItem, item_id)
        if not item:
            return False
        item.processed = False
        await session.commit()
        count = await _process_batch(session, limit=1)
        return count > 0
