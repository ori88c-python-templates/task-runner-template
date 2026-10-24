"""``OUTPUT_DIR_PATH`` is a directory shape, and ``REPORT_PATH`` adds today's file."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import GithubReportConfig


def test_report_path_is_todays_csv_under_the_default_directory() -> None:
    """The filename, including the UTC date, is added in code."""
    day = datetime.now(UTC).strftime("%Y_%m_%d")

    path = GithubReportConfig().REPORT_PATH
    assert path.parent == Path("github_reports")
    assert path.name == f"{day}_popular_github_repos.csv"


def test_a_directory_that_does_not_exist_is_accepted() -> None:
    """The writer creates the directory later, so config does not look at the disk."""
    config = GithubReportConfig(OUTPUT_DIR_PATH="reports/not-created-yet")

    assert config.REPORT_PATH.parent == Path("reports/not-created-yet")


def test_blank_directory_is_rejected() -> None:
    """An empty path has nowhere to put the file."""
    with pytest.raises(ValidationError, match="must name a directory"):
        GithubReportConfig(OUTPUT_DIR_PATH="   ")


def test_parent_segment_is_rejected() -> None:
    """``..`` would let the setting escape the directory it names."""
    with pytest.raises(ValidationError, match="must not contain"):
        GithubReportConfig(OUTPUT_DIR_PATH="github_reports/../secret")


def test_a_csv_file_path_is_rejected() -> None:
    """The dated filename is not part of the setting."""
    with pytest.raises(ValidationError, match="not a CSV file"):
        GithubReportConfig(OUTPUT_DIR_PATH="github_reports/2026_10_23_popular_github_repos.csv")
