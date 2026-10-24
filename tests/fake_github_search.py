"""Shared GitHub Search API doubles for unit tests.

The JSON is a real two-item search payload, trimmed of optional fields the SDK
does not require. ``mock_github`` serves it over ``httpx.MockTransport`` so no
test binds a socket or spends a search-rate-limit slot. ``build_client_factory``
wraps that SDK in a real ``GithubClient``.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import httpx
from githubkit import GitHub
from githubkit.auth import TokenAuthStrategy, UnauthAuthStrategy

from app.clients import GithubClient
from app.config import GithubReportConfig
from app.logger import LogManager

_FAKE_PATH: Final = Path(__file__).with_name("fake_github_search.json")

FAKE_GITHUB_SEARCH: Final[dict[str, Any]] = json.loads(_FAKE_PATH.read_text(encoding="utf-8"))

FAKE_RATE_LIMIT: Final[dict[str, Any]] = {
    "resources": {
        "core": {"limit": 60, "remaining": 59, "reset": 1700000000, "used": 1},
        "search": {"limit": 10, "remaining": 9, "reset": 1700000000, "used": 1},
    }
}

_RATE_LIMIT_PATH: Final = "/rate_limit"
_SEARCH_PATH: Final = "/search/repositories"


@dataclass
class MockGithub:
    """A githubkit client on ``MockTransport``, plus the requests it received.

    Attributes:
        github: Pass this to ``GithubClient(..., github=...)``.
        requests: Every HTTP request the transport handled, in order.
    """

    github: GitHub[Any]
    requests: list[httpx.Request] = field(default_factory=lambda: [])


def mock_github(
    *,
    token: str | None = None,
    search_status: int = 200,
    search_body: dict[str, Any] | None = None,
    incomplete_results: bool | None = None,
) -> MockGithub:
    """Build an SDK instance that answers ``/rate_limit`` and ``/search/repositories``.

    Retries are off: a 503 in a unit test should surface as ``RequestFailed``, not
    wait through githubkit's default three-attempt backoff.

    Args:
        token: When set, the client sends ``Authorization: token ...``. When omitted,
            the request is unauthenticated, matching production without a token.
        search_status: HTTP status for the search endpoint. ``/rate_limit`` is
            always 200.
        search_body: JSON body for the search endpoint. Defaults to
            ``FAKE_GITHUB_SEARCH``.
        incomplete_results: Override the ``incomplete_results`` flag on the default
            body. Ignored when ``search_body`` is supplied.

    Returns:
        The SDK instance and the list that will collect every request it makes.
    """
    body = search_body if search_body is not None else dict(FAKE_GITHUB_SEARCH)
    if search_body is None and incomplete_results is not None:
        body["incomplete_results"] = incomplete_results

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Route the two endpoints the client uses and record the request.

        Args:
            request: The outgoing call githubkit built.

        Returns:
            A canned response, or 404 for any other path.
        """
        requests.append(request)
        path = request.url.path
        if path.endswith(_RATE_LIMIT_PATH):
            return httpx.Response(200, json=FAKE_RATE_LIMIT)
        if path.endswith(_SEARCH_PATH):
            return httpx.Response(search_status, json=body)
        return httpx.Response(404, json={"message": "Not Found"})

    auth = TokenAuthStrategy(token) if token is not None else UnauthAuthStrategy()
    github = GitHub(
        auth,
        async_transport=httpx.MockTransport(handler),
        http_cache=False,
        auto_retry=False,
    )
    return MockGithub(github=github, requests=requests)


MakeClient = Callable[..., tuple[GithubClient, MockGithub]]


def build_client_factory(log_manager: LogManager) -> MakeClient:
    """Return a factory that wraps ``mock_github`` in a real ``GithubClient``.

    Args:
        log_manager: Shared test manager; the client's records land on ``sink``.

    Returns:
        A callable of the same keyword arguments as ``mock_github``, plus an
        optional ``config``, that returns the client and the mock it talks to.
    """

    def factory(
        config: GithubReportConfig | None = None,
        **mock_kwargs: Any,
    ) -> tuple[GithubClient, MockGithub]:
        """Construct the client around a fresh mock transport.

        Args:
            config: Token and timeout. Defaults to the demo values.
            **mock_kwargs: Forwarded to ``mock_github``.

        Returns:
            The client under test and the mock that recorded its requests.
        """
        mocked = mock_github(**mock_kwargs)
        client = GithubClient(
            config if config is not None else GithubReportConfig(),
            log_manager.get_child_logger("GithubClient"),
            github=mocked.github,
        )
        return client, mocked

    return factory
