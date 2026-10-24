"""The adapter maps search items and translates GitHub's unknown-org 422."""

from io import BytesIO
from typing import Any

import pytest
from githubkit.exception import RequestFailed

from app.clients import GithubClient
from app.config import GithubReportConfig
from app.logger import LogManager
from app.models import GithubRepoInfo
from app.services import GithubAdapter, GithubOrganizationNotFoundError
from tests.fake_github_search import build_client_factory
from tests.log_records import read_records


async def _started_adapter(
    log_manager: LogManager,
    config: GithubReportConfig | None = None,
    **mock_kwargs: Any,
) -> tuple[GithubAdapter, GithubClient]:
    """Build an adapter whose client is already started on the mock transport.

    Args:
        log_manager: Shared test manager.
        config: Org and limit. Defaults to the demo values.
        **mock_kwargs: Forwarded to ``mock_github``.

    Returns:
        The adapter under test and the client the caller must ``stop``.
    """
    resolved = config if config is not None else GithubReportConfig()
    client, _mocked = build_client_factory(log_manager)(resolved, **mock_kwargs)
    await client.start()
    adapter = GithubAdapter(client, resolved, log_manager.get_child_logger("GithubAdapter"))
    return adapter, client


async def test_items_map_to_repo_info_including_missing_language(
    log_manager: LogManager,
    sink: BytesIO,
) -> None:
    """Stars, forks, and a ``None`` language survive the mapping in search order."""
    adapter, client = await _started_adapter(log_manager)

    try:
        repos = await adapter.get_popular_repos()
    finally:
        await client.stop()

    assert repos == [
        GithubRepoInfo(name="vscode", stars=1234, forks=567, language="TypeScript"),
        GithubRepoInfo(name="docs", stars=98, forks=12, language=None),
    ]
    (record,) = [
        record
        for record in read_records(sink)
        if record["msg"] == "github_adapter.popular_repos.fetched"
    ]
    assert record["org"] == "microsoft"
    assert record["count"] == 2


async def test_http_422_becomes_organization_not_found(log_manager: LogManager) -> None:
    """GitHub answers an unknown org with 422; callers see a domain error."""
    adapter, client = await _started_adapter(
        log_manager,
        search_status=422,
        search_body={"message": "Validation Failed"},
    )

    try:
        with pytest.raises(GithubOrganizationNotFoundError, match="microsoft") as exc_info:
            await adapter.get_popular_repos()
    finally:
        await client.stop()

    assert exc_info.value.org == "microsoft"


async def test_http_503_propagates_as_request_failed(log_manager: LogManager) -> None:
    """A server error is not an unknown org and is not swallowed."""
    adapter, client = await _started_adapter(
        log_manager,
        search_status=503,
        search_body={"message": "Service Unavailable"},
    )

    try:
        with pytest.raises(RequestFailed):
            await adapter.get_popular_repos()
    finally:
        await client.stop()
