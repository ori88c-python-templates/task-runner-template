"""Teardown follows the task however the task ends."""

from io import BytesIO

import pytest

from app.lifecycle import LifecycleManager
from tests.log_records import read_messages


async def test_startup_precedes_the_run_and_teardown_follows_it(
    lifecycle_manager: LifecycleManager,
    sink: BytesIO,
) -> None:
    """The runner runs between resource initialization and teardown, never outside."""
    async with lifecycle_manager.create_task_runner() as task_runner:
        await task_runner.run()

    assert read_messages(sink) == [
        "lifecycle.task_runner.creating",
        "lifecycle.app_state.building",
        "lifecycle.resources.initializing",
        "github.starting",
        "github.started",
        "task_runner.run.started",
        "github.search.completed",
        "github_adapter.popular_repos.fetched",
        "csv_report.written",
        "task_runner.run.completed",
        "lifecycle.resources.tearing_down",
        "github.stopping",
        "github.stopped",
    ]


async def test_teardown_runs_when_the_task_raises(
    lifecycle_manager: LifecycleManager,
    sink: BytesIO,
) -> None:
    """A failing task still releases resources, and its exception still propagates."""
    with pytest.raises(RuntimeError, match="boom"):
        async with lifecycle_manager.create_task_runner():
            raise RuntimeError("boom")

    assert read_messages(sink)[-3:] == [
        "lifecycle.resources.tearing_down",
        "github.stopping",
        "github.stopped",
    ]
