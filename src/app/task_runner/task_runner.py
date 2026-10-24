"""The orchestrator of one run: which services run, and in which order."""

from typing import Final

from structlog.typing import FilteringBoundLogger

from app.state import AppServices


class TaskRunner:
    """Orchestrates one run: invokes the services on ``AppServices`` in the order needed.

    Keep this class thin. It decides what runs and in which order; the work of each step
    lives in a service, so every step is unit-tested on its own and this class is tested
    with ``AsyncMock`` services. Data transformation, retries, loops over records, or any
    I/O here means a service is missing.

    It receives services only, never clients: reaching a client from here would put
    business logic in the orchestrator.
    """

    def __init__(self, services: AppServices, logger: FilteringBoundLogger) -> None:
        """Store the started services and the injected logger.

        Args:
            services: Built and started by the composition root before this runner exists.
            logger: Child logger named after this class.
        """
        self._services: Final = services
        self._logger: Final = logger

    async def run(self) -> None:
        """Fetch the popular repositories, then write them to the CSV report.

        The adapter's list is the writer's input. Neither step's work lives here.
        """
        self._logger.info("task_runner.run.started")
        repos = await self._services.github_adapter.get_popular_repos()
        await self._services.csv_report_writer.write(repos)
        self._logger.info("task_runner.run.completed", repos=len(repos))
