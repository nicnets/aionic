"""
GitHub collector. Fetches recently-updated AI/ML repositories via GitHub Search API.
Requires GITHUB_TOKEN for higher rate limits (5000/hr vs 60/hr).
"""
import logging
from datetime import datetime, timedelta, timezone

import httpx

from backend.collectors.base import BaseCollector, RawItemData

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com/search/repositories"
AI_TOPICS = [
    "llm+language:python",
    "machine-learning+language:python",
    "transformer+language:python",
    "diffusion-model",
    "multimodal-ai",
]
MAX_PER_QUERY = 30


class GitHubCollector(BaseCollector):
    source_name = "github"

    async def fetch_items(self) -> list[RawItemData]:
        headers = {"Accept": "application/vnd.github+json"}
        if token := self._cfg("github_token"):
            headers["Authorization"] = f"Bearer {token}"

        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        seen: set[str] = set()
        items: list[RawItemData] = []

        async with httpx.AsyncClient(headers=headers, timeout=20) as client:
            for topic in AI_TOPICS:
                try:
                    resp = await client.get(
                        GITHUB_API,
                        params={
                            "q": f"topic:{topic} pushed:>{cutoff} stars:>50",
                            "sort": "updated",
                            "order": "desc",
                            "per_page": MAX_PER_QUERY,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception:
                    logger.exception("GitHub query failed: %s", topic)
                    continue

                for repo in data.get("items", []):
                    repo_id = str(repo.get("id", ""))
                    if not repo_id or repo_id in seen:
                        continue
                    seen.add(repo_id)

                    pushed = repo.get("pushed_at")
                    published_at = None
                    if pushed:
                        try:
                            published_at = datetime.fromisoformat(
                                pushed.replace("Z", "+00:00")
                            )
                        except ValueError:
                            pass

                    items.append(
                        RawItemData(
                            source_id=repo_id,
                            url=repo.get("html_url"),
                            title=repo.get("full_name"),
                            content=repo.get("description") or "",
                            author=repo.get("owner", {}).get("login"),
                            published_at=published_at,
                            raw_metadata={
                                "stars": repo.get("stargazers_count", 0),
                                "forks": repo.get("forks_count", 0),
                                "language": repo.get("language"),
                                "topics": repo.get("topics", []),
                                "open_issues": repo.get("open_issues_count", 0),
                            },
                        )
                    )

        return items
