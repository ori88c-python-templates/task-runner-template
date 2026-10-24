"""Process entry point."""

import asyncio

from app.config import AppConfig
from app.lifecycle import LifecycleManager


def main() -> None:
    """Load configuration, install process hooks, and run the task to completion.

    Configuration is read first and separately so that an invalid environment fails
    here, before a single resource is constructed. The exit code is the outcome of the
    run.
    """
    app_config = AppConfig()
    lifecycle = LifecycleManager(app_config)
    lifecycle.install_process_logging()
    asyncio.run(_run(lifecycle))


async def _run(lifecycle: LifecycleManager) -> None:
    """Run the task runner, with every resource started before it and torn down after.

    Business logic belongs in ``TaskRunner`` and the services it orchestrates, so this
    function does not change as the task grows.

    Args:
        lifecycle: The composition root. Teardown runs when the ``async with`` exits.
    """
    async with lifecycle.create_task_runner() as task_runner:
        await task_runner.run()


if __name__ == "__main__":
    main()
