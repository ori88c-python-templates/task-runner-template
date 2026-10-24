"""The yielded runner shares the manager's logging pipeline."""

from io import BytesIO

from app.lifecycle import LifecycleManager
from tests.log_records import read_records


async def test_yielded_runner_logs_into_the_managers_stream(
    lifecycle_manager: LifecycleManager,
    sink: BytesIO,
) -> None:
    """The runner's child logger writes to the same stream as the lifecycle itself."""
    async with lifecycle_manager.create_task_runner() as task_runner:
        await task_runner.run()

    contexts = {record["context"] for record in read_records(sink)}
    assert {"LifecycleManager", "TaskRunner"} <= contexts
