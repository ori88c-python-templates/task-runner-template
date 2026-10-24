"""Translate GitHub search results into the report's repository records."""

from typing import Final

from githubkit.exception import RequestFailed
from structlog.typing import FilteringBoundLogger

from app.clients import GithubClient
from app.config import GithubReportConfig
from app.models import GithubRepoInfo
from app.services.github.github_adapter_errors import GithubOrganizationNotFoundError

_ORGANIZATION_NOT_FOUND_STATUS: Final = 422


class GithubAdapter:
    """Fetch the most-starred repositories of the configured organization.

    Knows the GitHub-specific shape (search items, the 422-for-unknown-org convention)
    so the ``TaskRunner`` and the writer never have to.
    """

    def __init__(
        self,
        github_client: GithubClient,
        config: GithubReportConfig,
        logger: FilteringBoundLogger,
    ) -> None:
        """Store the client, the org and limit, and the injected logger.

        Args:
            github_client: Already-started client that talks to GitHub.
            config: Which organization and how many repositories to fetch. Read here
                rather than passed per call because a run reports on one org.
            logger: Child logger named after this class.
        """
        self._github_client: Final = github_client
        self._config: Final = config
        self._logger: Final = logger

    async def get_popular_repos(self) -> list[GithubRepoInfo]:
        """Return the configured organization's most-starred public repositories.

        Returns:
            One record per repository, already in descending star order. Empty when
            the organization has no public repositories.

        Raises:
            GithubOrganizationNotFoundError: If GitHub does not know the organization
                or it is not visible.
            RequestFailed: If GitHub rejects the request for any other reason.
        """
        org = self._config.ORG_NAME
        try:
            items = await self._github_client.search_repositories_by_stars(
                org,
                self._config.REPOS_LIMIT,
            )
        except RequestFailed as exc:
            if exc.response.status_code == _ORGANIZATION_NOT_FOUND_STATUS:
                raise GithubOrganizationNotFoundError(org) from exc
            raise

        repos = [
            GithubRepoInfo(
                name=item.name,
                stars=item.stargazers_count,
                forks=item.forks_count,
                language=item.language,
            )
            for item in items
        ]
        self._logger.info(
            "github_adapter.popular_repos.fetched",
            org=org,
            count=len(repos),
        )
        return repos
