"""``python -m app.main`` writes the CSV report and exits 0."""

import csv
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def test_run_writes_the_popular_repos_csv_and_exits_zero(tmp_path: Path) -> None:
    """A temp cwd keeps the developer's ``.env`` out; the token is passed through.

    Args:
        tmp_path: Empty working directory so ``AppConfig`` does not read a local
            ``.env``, and so the CSV is not written into the repository.
    """
    env = {
        **os.environ,
        "GITHUB_REPORT__REPOS_LIMIT": "3",
        "LOGGER__MIN_LOG_LEVEL": "info",
    }
    token = os.environ.get("GITHUB_REPORT__TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        env["GITHUB_REPORT__TOKEN"] = token

    result = subprocess.run(
        [sys.executable, "-m", "app.main"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "lifecycle.task_runner.creating" in result.stdout
    assert "csv_report.written" in result.stdout
    assert "task_runner.run.completed" in result.stdout

    filename = f"{datetime.now(UTC):%Y_%m_%d}_popular_github_repos.csv"
    path = tmp_path / "github_reports" / filename
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    assert rows[0] == ["rank", "name", "stars", "forks", "language"]
    data = rows[1:]
    assert [row[0] for row in data] == ["1", "2", "3"]
    stars = [int(row[2]) for row in data]
    assert stars == sorted(stars, reverse=True)
    assert all(row[1] for row in data)
