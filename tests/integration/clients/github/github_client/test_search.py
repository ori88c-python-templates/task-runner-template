"""Search the real GitHub API for an organization's most-starred repositories."""

from app.clients import GithubClient
from app.logger import LogManager
from tests.load_app_config import load_app_config

_ORG: str = "microsoft"
_LIMIT: int = 3


async def test_search_returns_repos_in_non_increasing_star_order(
    log_manager: LogManager,
) -> None:
    """Three Microsoft repositories come back already ranked by stars."""
    client = GithubClient(
        load_app_config().github_report,
        log_manager.get_child_logger("GithubClient"),
    )
    await client.start()
    try:
        items = await client.search_repositories_by_stars(_ORG, _LIMIT)
    finally:
        await client.stop()

    assert len(items) == _LIMIT
    stars = [item.stargazers_count for item in items]
    assert stars == sorted(stars, reverse=True)
    assert all(item.name for item in items)
