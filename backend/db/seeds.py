"""
Seed default data on first startup.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.models import SourceWeight, AIProviderConfig, SystemConfig, RssFeed

DEFAULT_SOURCE_WEIGHTS = {
    "arxiv": 1.0,
    "github": 0.9,
    "hn": 0.8,
    "stackoverflow": 0.8,
    "huggingface": 0.8,
    "newsapi": 0.7,
    "rss": 0.7,
    "producthunt": 0.6,
    "google_trends": 0.6,
    "reddit": 0.5,
}


async def seed_source_weights(session: AsyncSession) -> None:
    count = await session.scalar(
        select(func.count()).select_from(SourceWeight)
    )
    if count and count > 0:
        return
    for source, weight in DEFAULT_SOURCE_WEIGHTS.items():
        session.add(SourceWeight(source=source, weight=weight, updated_by="system"))
    await session.commit()


async def seed_ai_provider(session: AsyncSession) -> None:
    count = await session.scalar(
        select(func.count()).select_from(AIProviderConfig)
    )
    if count and count > 0:
        return
    session.add(AIProviderConfig(
        provider="claude",
        model_id="claude-haiku-4-5-20251001",
        is_active=True,
    ))
    await session.commit()


# (key, default_value, is_secret, category, description)
_SYSTEM_CONFIG_DEFAULTS: list[tuple[str, str, bool, str, str]] = [
    # LLM
    ("anthropic_api_key",             "",            True,  "llm",        "Anthropic API key for Claude models"),
    ("openai_api_key",                "",            True,  "llm",        "OpenAI API key"),
    ("openrouter_api_key",            "",            True,  "llm",        "OpenRouter API key"),
    # Collectors
    ("reddit_client_id",              "",            True,  "collectors", "Reddit OAuth2 client ID"),
    ("reddit_client_secret",          "",            True,  "collectors", "Reddit OAuth2 client secret"),
    ("reddit_user_agent",             "aionic/1.0",  False, "collectors", "Reddit API user-agent string"),
    ("newsapi_key",                   "",            True,  "collectors", "NewsAPI.org API key"),
    ("github_token",                  "",            True,  "collectors", "GitHub personal access token (raises rate limit to 5000/hr)"),
    ("huggingface_token",             "",            True,  "collectors", "Hugging Face API token"),
    # Scheduling
    ("collect_rss_interval_hours",         "1",  False, "scheduling", "RSS collection interval (hours)"),
    ("collect_reddit_interval_hours",      "2",  False, "scheduling", "Reddit collection interval (hours)"),
    ("collect_hn_interval_hours",          "2",  False, "scheduling", "Hacker News collection interval (hours)"),
    ("collect_newsapi_interval_hours",     "4",  False, "scheduling", "NewsAPI collection interval (hours)"),
    ("collect_github_interval_hours",      "4",  False, "scheduling", "GitHub collection interval (hours)"),
    ("collect_arxiv_interval_hours",       "6",  False, "scheduling", "arXiv collection interval (hours)"),
    ("collect_huggingface_interval_hours", "6",  False, "scheduling", "HuggingFace collection interval (hours)"),
    ("collect_stackoverflow_interval_hours","6", False, "scheduling", "StackOverflow collection interval (hours)"),
    ("collect_google_trends_cron_hour",    "2",  False, "scheduling", "Google Trends collection hour (0–23 UTC)"),
    # Processing
    ("processing_batch_size",         "500",         False, "processing", "Items per processing batch"),
    ("llm_importance_threshold",      "0.70",        False, "processing", "Minimum importance score before sending to LLM (0–1)"),
    ("llm_cache_ttl_seconds",         "604800",      False, "processing", "LLM response cache TTL in seconds (default 7 days)"),
]


async def seed_system_config(session: AsyncSession) -> None:
    count = await session.scalar(
        select(func.count()).select_from(SystemConfig)
    )
    if count and count > 0:
        return
    for key, value, is_secret, category, description in _SYSTEM_CONFIG_DEFAULTS:
        session.add(SystemConfig(
            key=key,
            value=value,
            is_secret=is_secret,
            category=category,
            description=description,
        ))
    await session.commit()


# (url, name, category)
_DEFAULT_RSS_FEEDS: list[tuple[str, str, str]] = [
    # Research / preprints
    ("https://arxiv.org/rss/cs.AI",                                "arXiv — AI",                "research"),
    ("https://arxiv.org/rss/cs.LG",                                "arXiv — Machine Learning",  "research"),
    ("https://arxiv.org/rss/cs.CL",                                "arXiv — NLP",               "research"),
    ("https://arxiv.org/rss/cs.CV",                                "arXiv — Computer Vision",   "research"),
    ("https://paperswithcode.com/latest.rss",                      "Papers With Code",          "research"),
    # Lab blogs
    ("https://openai.com/blog/rss.xml",                            "OpenAI Blog",               "lab"),
    ("https://www.anthropic.com/rss.xml",                          "Anthropic Blog",            "lab"),
    ("https://huggingface.co/blog/feed.xml",                       "Hugging Face Blog",         "lab"),
    ("https://bair.berkeley.edu/blog/feed.xml",                    "BAIR Blog",                 "lab"),
    ("https://blog.research.google/feeds/posts/default",           "Google Research Blog",      "lab"),
    ("https://deepmind.google/blog/rss.xml",                       "Google DeepMind Blog",      "lab"),
    # Tech media
    ("https://venturebeat.com/category/ai/feed/",                  "VentureBeat AI",            "media"),
    ("https://techcrunch.com/category/artificial-intelligence/feed/", "TechCrunch AI",          "media"),
    ("https://thenextweb.com/neural/feed/",                        "The Next Web — Neural",     "media"),
    ("https://www.technologyreview.com/topic/artificial-intelligence/feed", "MIT Tech Review AI", "media"),
    ("https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss", "IEEE Spectrum AI",   "media"),
    # Community / newsletters
    ("https://www.deeplearning.ai/the-batch/feed/",                "DeepLearning.AI The Batch", "community"),
    ("https://syncedreview.com/feed/",                             "Synced Review",             "community"),
    ("https://www.marktechpost.com/feed/",                         "MarkTechPost",              "community"),
    ("https://machinelearningmastery.com/feed/",                   "Machine Learning Mastery",  "community"),
    ("https://towardsdatascience.com/feed",                        "Towards Data Science",      "community"),
]


async def seed_rss_feeds(session: AsyncSession) -> None:
    count = await session.scalar(
        select(func.count()).select_from(RssFeed)
    )
    if count and count > 0:
        return
    for url, name, category in _DEFAULT_RSS_FEEDS:
        session.add(RssFeed(url=url, name=name, category=category, is_active=True))
    await session.commit()


async def run_all_seeds(session: AsyncSession) -> None:
    from backend.topics.seed_topics import seed_topics
    await seed_source_weights(session)
    await seed_ai_provider(session)
    await seed_system_config(session)
    await seed_topics(session)
    await seed_rss_feeds(session)
