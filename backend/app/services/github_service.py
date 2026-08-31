from datetime import UTC, datetime, timedelta

import httpx

from app.core.config import get_settings


async def search_github_repos(query: str, *, limit: int = 5) -> dict:
    """Live GitHub repository search. Standalone extraction of chat_tools.github_search's
    HTTP call so both the LangChain tool and the background suggestion job
    (github_cache_service.py) share one implementation. Returns real, currently
    well-maintained repos above a minimum star count that pushed a commit within roughly
    the configured freshness window and are not archived — same shape as before:
    {"repos": [...], "query_used": str, "error"?: str}."""
    settings = get_settings()
    limit = min(max(limit, 1), 10)
    cutoff = (datetime.now(UTC) - timedelta(days=settings.github_freshness_months * 30)).strftime("%Y-%m-%d")
    search_query = (
        f"{query} in:name,description,topics "
        f"stars:>={settings.github_min_stars} archived:false pushed:>={cutoff}"
    )
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://api.github.com/search/repositories",
                params={"q": search_query, "sort": "stars", "order": "desc", "per_page": limit},
                headers=headers,
            )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        return {"repos": [], "query_used": search_query, "error": f"GitHub search is unreachable: {exc}"}

    if response.status_code in (403, 429):
        return {
            "repos": [],
            "query_used": search_query,
            "error": "GitHub search is rate-limited right now, try again shortly.",
            "rate_limited": True,
        }
    if response.status_code != 200:
        return {
            "repos": [],
            "query_used": search_query,
            "error": f"GitHub search failed (status {response.status_code}).",
        }

    items = response.json().get("items", [])
    repos = [
        {
            "name": item["name"],
            "full_name": item["full_name"],
            "url": item["html_url"],
            # Truncated before it ever reaches the model/UI — bounds how much
            # attacker-influenced text (repo descriptions are third-party content) can
            # ride along per repo.
            "description": (item.get("description") or "")[:300],
            "stars": item["stargazers_count"],
            "language": item.get("language"),
            "pushed_at": item.get("pushed_at"),
            "archived": item.get("archived", False),
        }
        for item in items
        if not item.get("archived")
    ]
    return {"repos": repos, "query_used": search_query}
