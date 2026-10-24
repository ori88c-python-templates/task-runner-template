"""The organization login is taken from a github.com URL of exactly one segment."""

import pytest
from pydantic import ValidationError

from app.config import GithubReportConfig


def test_org_name_is_the_single_path_segment() -> None:
    """The default Microsoft URL yields the login the Search API expects."""
    assert GithubReportConfig().ORG_NAME == "microsoft"


def test_trailing_slash_is_ignored() -> None:
    """A copy-pasted URL with a trailing slash still names the organization."""
    config = GithubReportConfig.model_validate({"ORG_URL": "https://github.com/microsoft/"})

    assert config.ORG_NAME == "microsoft"


def test_non_github_host_is_rejected() -> None:
    """A GitLab or other host is not a GitHub organization URL."""
    with pytest.raises(ValidationError, match=r"must point at github\.com"):
        GithubReportConfig.model_validate({"ORG_URL": "https://gitlab.com/microsoft"})


def test_site_root_is_rejected() -> None:
    """``https://github.com/`` names no organization."""
    with pytest.raises(ValidationError, match="must name an organization"):
        GithubReportConfig.model_validate({"ORG_URL": "https://github.com/"})


def test_repository_url_is_rejected() -> None:
    """Two path segments is a repository, not an organization."""
    with pytest.raises(ValidationError, match="not a repository URL"):
        GithubReportConfig.model_validate({"ORG_URL": "https://github.com/microsoft/vscode"})
