"""Shared models passed between the ``TaskRunner``, services, and clients."""

from app.models.github.github_repo_info import GithubRepoInfo

__all__ = ["GithubRepoInfo"]
