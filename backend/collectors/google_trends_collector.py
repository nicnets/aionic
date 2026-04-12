"""
Google Trends collector. Uses pytrends (sync) via thread executor.
Fetches interest-over-time data for key AI topics.
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timezone

from backend.collectors.base import BaseCollector, RawItemData

logger = logging.getLogger(__name__)

TREND_KEYWORDS = [
    ["ChatGPT", "Claude", "Gemini"],
    ["LLM", "RAG", "fine-tuning"],
    ["AI agents", "multimodal AI", "AI safety"],
    ["Stable Diffusion", "Midjourney", "Sora"],
    ["GPT-4", "llama", "mistral"],
]


def _fetch_trends_sync(keyword_group: list[str]) -> list[dict]:
    """Synchronous pytrends call — runs in thread executor."""
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
        pt.build_payload(keyword_group, timeframe="now 7-d", geo="")
        df = pt.interest_over_time()
        if df is None or df.empty:
            return []

        items = []
        for kw in keyword_group:
            if kw not in df.columns:
                continue
            series = df[kw]
            avg_interest = float(series.mean())
            peak_interest = int(series.max())
            source_id = hashlib.md5(f"gtrends:{kw}:{df.index[-1].date()}".encode()).hexdigest()
            items.append(
                {
                    "source_id": source_id,
                    "keyword": kw,
                    "avg_interest": avg_interest,
                    "peak_interest": peak_interest,
                    "period_end": df.index[-1].to_pydatetime().replace(tzinfo=timezone.utc),
                    "data_points": series.tolist(),
                }
            )
        return items
    except Exception as exc:
        logger.warning("Google Trends fetch failed for %s: %s", keyword_group, exc)
        return []


class GoogleTrendsCollector(BaseCollector):
    source_name = "google_trends"

    async def fetch_items(self) -> list[RawItemData]:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, _fetch_trends_sync, group)
            for group in TREND_KEYWORDS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        items: list[RawItemData] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Google Trends task error: %s", result)
                continue
            for row in result:
                items.append(
                    RawItemData(
                        source_id=row["source_id"],
                        url=None,
                        title=f"Google Trends: {row['keyword']}",
                        content=(
                            f"Keyword: {row['keyword']}. "
                            f"Average interest (7d): {row['avg_interest']:.1f}/100. "
                            f"Peak: {row['peak_interest']}/100."
                        ),
                        author=None,
                        published_at=row["period_end"],
                        raw_metadata={
                            "keyword": row["keyword"],
                            "avg_interest": row["avg_interest"],
                            "peak_interest": row["peak_interest"],
                            "data_points": row["data_points"],
                        },
                    )
                )
        return items
