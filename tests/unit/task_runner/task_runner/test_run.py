"""``run`` awaits the adapter, then the writer, and brackets the work with logs."""

from collections.abc import Sequence
from io import BytesIO
from unittest.mock import AsyncMock

from app.logger import LogManager
from app.models import GithubRepoInfo
from app.services import CsvReportWriter, GithubAdapter
from app.state import AppServices
from app.task_runner import TaskRunner
from tests.log_records import read_records

_REPOS = [
    GithubRepoInfo(name="vscode", stars=1234, forks=567, language="TypeScript"),
]


async def test_run_passes_the_adapter_result_to_the_writer(
    log_manager: LogManager,
    sink: BytesIO,
) -> None:
    """The writer's argument is exactly the adapter's return value, after it."""
    order: list[str] = []
    written: list[Sequence[GithubRepoInfo]] = []

    async def get_popular_repos() -> list[GithubRepoInfo]:
        """Record that the adapter ran, then return the canned list.

        Returns:
            The repositories the writer must receive.
        """
        order.append("adapter")
        return _REPOS

    async def write(repos: Sequence[GithubRepoInfo]) -> None:
        """Record that the writer ran, and what it was given.

        Args:
            repos: Whatever the runner passed through.
        """
        order.append("writer")
        written.append(repos)

    adapter = AsyncMock(spec=GithubAdapter)
    adapter.get_popular_repos.side_effect = get_popular_repos
    writer = AsyncMock(spec=CsvReportWriter)
    writer.write.side_effect = write
    task_runner = TaskRunner(
        AppServices(github_adapter=adapter, csv_report_writer=writer),
        log_manager.get_child_logger("TaskRunner"),
    )

    await task_runner.run()

    assert order == ["adapter", "writer"]
    assert written == [_REPOS]
    records = read_records(sink)
    assert [record["msg"] for record in records] == [
        "task_runner.run.started",
        "task_runner.run.completed",
    ]
    assert records[1]["repos"] == 1
    assert {record["context"] for record in records} == {"TaskRunner"}
