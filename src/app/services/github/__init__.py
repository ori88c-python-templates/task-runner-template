"""GitHub-facing services: the adapter that turns search results into report records."""

from app.services.github.github_adapter import GithubAdapter
from app.services.github.github_adapter_errors import GithubOrganizationNotFoundError

__all__ = [
    "GithubAdapter",
    "GithubOrganizationNotFoundError",
]
