"""Wrapper around the githubkit SDK with explicit lifecycle hooks."""

from contextlib import AsyncExitStack
from typing import Any, Final

from githubkit import GitHub
from githubkit.auth import BaseAuthStrategy, TokenAuthStrategy, UnauthAuthStrategy
from githubkit_schemas.latest.models import (  # pyright: ignore[reportMissingTypeStubs]
    RepoSearchResultItem,
)
from structlog.typing import FilteringBoundLogger

from app.config import APP_NAME, GithubReportConfig

_SORT_BY_STARS: Final = "stars"
_DESCENDING: Final = "desc"


class GithubClient:
    """Owns one GitHub SDK instance and its HTTP connection for the run.

    Construction does not talk to the network: ``GitHub`` is lazy. ``start`` opens the
    connection and proves it works, which is why it runs in the composition root's
    topological init rather than in ``__init__``.
    """

    def __init__(
        self,
        config: GithubReportConfig,
        logger: FilteringBoundLogger,
        *,
        github: GitHub[Any] | None = None,
    ) -> None:
        """Build the SDK instance. Does not connect.

        Args:
            config: Token and timeout. The token is consumed here and never logged.
            logger: Child logger named after this class.
            github: Pre-built SDK instance. Production leaves this unset; tests pass one
                on an ``httpx.MockTransport`` so nothing binds a real socket.
        """
        self._logger: Final = logger
        self._exit_stack: Final = AsyncExitStack()
        # githubkit's GitHub is invariant in its auth strategy, so Token | Unauth
        # cannot be typed as GitHub[BaseAuthStrategy]. Any is the seam tests use too.
        self._github: Final[GitHub[Any]] = (
            github if github is not None else self._build_github(config)
        )

    async def start(self) -> None:
        """Open the connection and confirm GitHub answers.

        ``GitHub`` is an async context manager (``async with GitHub()``). That block
        would close the connection when ``start`` returns, so the exit is held on an
        ``AsyncExitStack`` until ``stop``.

        The probe is ``GET /rate_limit``, which does not count against any quota. A
        missing network or a rejected token therefore fails the run at startup, not at
        the first real request.

        Raises:
            githubkit.exception.GitHubException: If GitHub cannot be reached or rejects
                the credentials. The composition root treats this as a failed startup.
        """
        self._logger.info("github.starting")
        await self._exit_stack.enter_async_context(self._github)
        response = await self._github.rest.rate_limit.async_get()
        resources = response.parsed_data.resources
        self._logger.info(
            "github.started",
            search_remaining=resources.search.remaining,
            core_remaining=resources.core.remaining,
        )

    async def stop(self) -> None:
        """Close the connection.

        Safe to call if ``start`` never ran or failed: an empty exit stack closes
        nothing.
        """
        self._logger.info("github.stopping")
        await self._exit_stack.aclose()
        self._logger.info("github.stopped")

    async def search_repositories_by_stars(
        self,
        org: str,
        limit: int,
    ) -> list[RepoSearchResultItem]:
        """Return the ``limit`` most-starred public repositories of ``org``.

        One request to the Search API, sorted server-side. ``GET /orgs/{org}/repos``
        cannot sort by stars, which is why search is used instead.

        Args:
            org: The organization's login, e.g. ``microsoft``.
            limit: How many repositories to return, at most 100 (one search page).

        Returns:
            Search result items in descending star order, at most ``limit`` of them.

        Raises:
            githubkit.exception.RequestFailed: If GitHub rejects the request. A 422
                means the organization does not exist or is not visible.
        """
        response = await self._github.rest.search.async_repos(
            q=f"org:{org}",
            sort=_SORT_BY_STARS,
            order=_DESCENDING,
            per_page=limit,
        )
        result = response.parsed_data
        self._logger.info(
            "github.search.completed",
            org=org,
            total_count=result.total_count,
            returned=len(result.items),
        )
        if result.incomplete_results:
            self._logger.warning("github.search.incomplete", org=org)
        return result.items

    @staticmethod
    def _build_github(config: GithubReportConfig) -> GitHub[Any]:
        """Build the production SDK instance from configuration.

        The HTTP cache is off: a run makes two requests and exits, so there is nothing
        for a cache to serve. The user agent names this app, as GitHub asks.

        Args:
            config: Token and timeout.

        Returns:
            An SDK instance that has not opened a connection yet.
        """
        auth: BaseAuthStrategy = (
            TokenAuthStrategy(config.TOKEN.get_secret_value())
            if config.TOKEN is not None
            else UnauthAuthStrategy()
        )
        return GitHub(
            auth,
            timeout=config.REQUEST_TIMEOUT_SECONDS,
            http_cache=False,
            user_agent=APP_NAME,
        )
