"""
Categorizer: assigns a category to a processed item.

Primary: rule-based keyword matching (fast, zero cost).
Fallback: use category from LLM enrichment if available.

Categories:
  research     — papers, findings, benchmarks, experiments
  tools        — libraries, frameworks, SDKs, APIs, open-source releases
  applications — products, demos, use cases, deployments
  news         — funding, acquisitions, announcements, policy
  community    — tutorials, discussions, blog posts, Q&A
"""
import re
from backend.db.models import RawItem

CATEGORY_RULES: list[tuple[str, list[str]]] = [
    (
        "research",
        [
            "arxiv", "paper", "preprint", "benchmark", "evaluation", "study",
            "experiment", "dataset", "model training", "ablation", "loss",
            "perplexity", "accuracy", "f1 score", "published in", "journal",
            "conference", "neurips", "icml", "iclr", "acl", "cvpr", "emnlp",
        ],
    ),
    (
        "tools",
        [
            "library", "framework", "sdk", "api", "open source", "open-source",
            "github", "package", "release", "version", "v1.", "v2.", "install",
            "pip install", "npm", "docker", "cli", "toolkit", "integration",
            "plugin", "extension", "hugging face", "langchain", "llamaindex",
        ],
    ),
    (
        "applications",
        [
            "product launch", "demo", "app", "chatbot", "assistant",
            "copilot", "agent", "automation", "deployment", "production",
            "use case", "customer", "enterprise", "saas", "platform launch",
            "integrates with", "powered by", "built with",
        ],
    ),
    (
        "news",
        [
            "funding", "raised", "series a", "series b", "ipo", "acquisition",
            "partnership", "announces", "regulation", "policy", "law",
            "eu ai act", "executive order", "ceo", "founded", "layoffs",
            "valuation", "billion", "investment",
        ],
    ),
    (
        "community",
        [
            "tutorial", "how to", "guide", "walkthrough", "explainer",
            "reddit", "hacker news", "discussion", "thread", "question",
            "blog post", "opinion", "thoughts on", "my experience",
            "stackoverflow", "forum", "community",
        ],
    ),
]

SOURCE_CATEGORY_DEFAULTS: dict[str, str] = {
    "arxiv": "research",
    "hn": "community",
    "stackoverflow": "community",
    "github": "tools",
    "huggingface": "tools",
    "google_trends": "news",
    "newsapi": "news",
    "rss": "news",
    "reddit": "community",
}


def categorize(item: RawItem, llm_category: str | None = None) -> str:
    """
    Assign a category. Rule-based first, then LLM hint, then source default.
    """
    text = f"{item.title or ''} {item.content or ''}".lower()

    # Score each category by keyword hits
    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_RULES:
        score = sum(1 for kw in keywords if kw in text)
        if score:
            scores[category] = score

    if scores:
        return max(scores, key=scores.__getitem__)

    # Use LLM hint if available and valid
    valid_categories = {"research", "tools", "applications", "news", "community"}
    if llm_category and llm_category in valid_categories:
        return llm_category

    # Fall back to source default
    return SOURCE_CATEGORY_DEFAULTS.get(item.source, "news")
