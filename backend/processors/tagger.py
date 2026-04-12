"""
Tagger: extracts canonical topics from a processed item.

Two-tier approach:
  1. Rule-based keyword scan — fast, zero cost, handles well-known topics
  2. LLM extraction — only for items above importance threshold
     (handled in pipeline.py, not here)

This module handles tier 1. Tier 2 (LLM) prompting is in summarizer.py
since we batch summarization + tagging in one LLM call.
"""
import logging
import re
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import RawItem, Topic, TopicMention
from backend.topics.canonicalizer import get_canonicalizer

logger = logging.getLogger(__name__)


async def tag_item(
    item: RawItem,
    session: AsyncSession,
    extra_topic_strings: list[str] | None = None,
) -> list[Topic]:
    """
    Extract and canonicalize topics from a single item.
    extra_topic_strings can be passed from LLM output.
    Returns list of matched canonical Topics.
    Also creates TopicMention records for each match.
    """
    canonicalizer = get_canonicalizer()

    # Collect candidate strings: title + content keywords + LLM extras
    candidates = _extract_candidates(item)
    if extra_topic_strings:
        candidates.extend(extra_topic_strings)

    # Deduplicate candidates (case-insensitive)
    seen_norm = set()
    unique_candidates = []
    for c in candidates:
        norm = c.lower().strip()
        if norm and norm not in seen_norm:
            seen_norm.add(norm)
            unique_candidates.append(c)

    # Resolve each candidate to a canonical topic
    matched: list[Topic] = []
    matched_ids: set[int] = set()

    for candidate in unique_candidates:
        topic = await canonicalizer.resolve(candidate, session)
        if topic and topic.id not in matched_ids:
            matched.append(topic)
            matched_ids.add(topic.id)

    # Create TopicMention records (skip if already exists — handled by uq constraint)
    for topic in matched:
        from sqlalchemy import select
        existing = await session.scalar(
            select(TopicMention).where(
                TopicMention.topic_id == topic.id,
                TopicMention.raw_item_id == item.id,
            )
        )
        if not existing:
            mention = TopicMention(
                topic_id=topic.id,
                raw_item_id=item.id,
                source=item.source,
                weight=1.0,
            )
            session.add(mention)

    await session.commit()
    return matched


def _extract_candidates(item: RawItem) -> list[str]:
    """
    Rule-based extraction of topic candidate strings from title + content.
    Returns a flat list of candidate strings (not yet canonicalized).
    """
    text = f"{item.title or ''} {item.content or ''}"
    candidates = []

    # 1. Match known AI topic keywords (simple substring scan)
    for kw in _AI_KEYWORDS:
        # Whole-word match (case-insensitive)
        if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
            candidates.append(kw)

    # 2. Extract capitalized multi-word phrases (likely named topics)
    # Pattern: 2–4 title-case words not at sentence start
    phrases = re.findall(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", text
    )
    candidates.extend(phrases[:20])  # cap to avoid noise

    # 3. Common acronyms
    acronyms = re.findall(r"\b([A-Z]{2,6})\b", text)
    candidates.extend(acronyms[:10])

    return candidates


# Well-known AI topic keywords (lower-case for matching)
_AI_KEYWORDS = [
    "large language model", "llm", "gpt", "claude", "gemini", "llama",
    "mistral", "fine-tuning", "rag", "retrieval augmented generation",
    "transformer", "attention mechanism", "neural network", "deep learning",
    "reinforcement learning", "rlhf", "reward model", "ai safety",
    "alignment", "hallucination", "prompt engineering", "chain of thought",
    "function calling", "tool use", "agents", "multi-agent",
    "diffusion model", "stable diffusion", "text to image", "image generation",
    "speech recognition", "text to speech", "multimodal", "vision language model",
    "computer vision", "object detection", "semantic segmentation",
    "embedding", "vector database", "semantic search", "knowledge graph",
    "model quantization", "pruning", "distillation", "lora", "qlora",
    "inference optimization", "speculative decoding", "mixture of experts",
    "moe", "constitutional ai", "rlaif", "dpo", "ppo",
    "openai", "anthropic", "google deepmind", "meta ai", "mistral ai",
    "hugging face", "langchain", "llamaindex", "ollama",
    "pytorch", "jax", "tensorflow", "triton",
    "gpu", "tpu", "cuda", "inference", "training",
    "benchmark", "mmlu", "hellaswag", "humaneval", "gsm8k",
    "robotics", "autonomous driving", "ai regulation", "eu ai act",
    "synthetic data", "data augmentation", "federated learning",
    "mlops", "model serving", "vllm", "tensorrt",
]
