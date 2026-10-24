"""Clients for external resources: the application's data access layer."""

from app.clients.github.github_client import GithubClient

__all__ = ["GithubClient"]
