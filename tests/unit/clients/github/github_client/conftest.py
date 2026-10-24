"""Build a ``GithubClient`` on the shared mock transport."""

import pytest

from app.logger import LogManager
from tests.fake_github_search import MakeClient, build_client_factory


@pytest.fixture
def make_client(log_manager: LogManager) -> MakeClient:
    """Provide a factory that wraps ``mock_github`` in a real ``GithubClient``.

    Args:
        log_manager: Shared test manager; the client's records land on ``sink``.

    Returns:
        The factory the tests call to get a client and its mock.
    """
    return build_client_factory(log_manager)
