"""Construction, startup and shutdown of the application state for one run."""

import asyncio
import sys
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, BinaryIO, Final

from githubkit import GitHub

from app.clients import GithubClient
from app.config import AppConfig
from app.distribution import installed_app_version
from app.lifecycle.cancel_on_sigterm import cancel_on_sigterm
from app.logger import (
    LogManager,
    install_stdlib_log_bridge,
    make_asyncio_exception_handler,
    make_sys_excepthook,
)
from app.services import CsvReportWriter, GithubAdapter
from app.state import AppClients, AppServices, AppState
from app.task_runner import TaskRunner

_LIFECYCLE_LOGGER_NAME: Final = "LifecycleManager"
_TASK_RUNNER_LOGGER_NAME: Final = "TaskRunner"
_GITHUB_CLIENT_LOGGER_NAME: Final = "GithubClient"
_GITHUB_ADAPTER_LOGGER_NAME: Final = "GithubAdapter"
_CSV_REPORT_WRITER_LOGGER_NAME: Final = "CsvReportWriter"
_STDLIB_LOGGER_NAME: Final = "stdlib"
_ASYNCIO_LOGGER_NAME: Final = "asyncio"
_SYS_EXCEPTHOOK_LOGGER_NAME: Final = "sys.excepthook"


class LifecycleManager:
    """Builds the application state and the ``TaskRunner`` on top of it.

    This is the composition root: the one place that constructs dependencies, hands them
    to each other, and owns the order their resources start and stop in. Nothing else in
    the codebase calls a constructor for a client, a service, the ``TaskRunner`` or a
    logger, which is what keeps the rest of the app free of global state.

    A class rather than a set of functions because every step wants the same two things,
    the configuration and a logger, and threading both through every function signature
    is noise. Built once, in ``main``.
    """

    def __init__(
        self,
        app_config: AppConfig,
        *,
        stream: BinaryIO | None = None,
        github: GitHub[Any] | None = None,
    ) -> None:
        """Prepare the manager and the logging every later step reports through.

        The ``LogManager`` is built here rather than during ``create_task_runner`` because
        it is the one dependency the manager itself needs: it has to be able to log the
        construction of everything else, including the failures.

        Args:
            app_config: Fully validated configuration, built by the caller so that a bad
                environment fails before anything is constructed.
            stream: Binary stream for ``LogManager``. Defaults to stdout. Tests pass a
                buffer so they can read the run's logs. Production omits it.
            github: Pre-built SDK. Production leaves this unset and the client builds its
                own. Tests pass one on a mock transport so no lifecycle unit test opens
                a socket. The client itself is still constructed here, with this
                manager's child logger.
        """
        self._app_config: Final = app_config
        self._github: Final = github
        self._log_manager: Final = LogManager(
            app_config.logger,
            env=app_config.ENV,
            app_version=installed_app_version(),
            stream=stream,
        )
        self._logger: Final = self._log_manager.get_child_logger(_LIFECYCLE_LOGGER_NAME)

    def install_process_logging(self) -> None:
        """Install ``sys.excepthook`` and the stdlib logging bridge, process-wide.

        Called from ``main``, not from ``create_task_runner``: an exception that escapes the
        task reaches ``sys.excepthook`` only after the context has exited, and tests that
        enter the context must not replace process hooks.
        """
        sys.excepthook = make_sys_excepthook(
            self._log_manager.get_child_logger(_SYS_EXCEPTHOOK_LOGGER_NAME),
        )
        install_stdlib_log_bridge(
            self._log_manager.get_child_logger(_STDLIB_LOGGER_NAME),
        )

    @asynccontextmanager
    async def create_task_runner(self) -> AsyncGenerator[TaskRunner]:
        """Build and start everything the run needs, yield the runner, then tear it down.

        The ``TaskRunner`` is built only after every client has started. ``AppState`` stays
        inside this method: the runner receives the services and nothing else.

        Teardown runs however the block ends: a normal exit, an exception, a failed
        startup, Ctrl+C, or SIGTERM, which then surfaces as ``SystemExit(143)``. The
        asyncio exception handler and the SIGTERM handler are scoped to the block.

        Yields:
            The runner of this run, valid until the ``async with`` block ends.

        Raises:
            RuntimeError: If entered outside an asyncio task, where there is nothing
                for SIGTERM to cancel.
        """
        self._logger.info("lifecycle.task_runner.creating")

        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("create_task_runner must be entered from an asyncio task.")

        app_state = self._build_app_state()
        with (
            self._asyncio_exception_logging(task.get_loop()),
            cancel_on_sigterm(task, self._logger),
        ):
            try:
                await self._init_by_topological_order(app_state)
                yield TaskRunner(
                    app_state.services,
                    self._log_manager.get_child_logger(_TASK_RUNNER_LOGGER_NAME),
                )
            finally:
                await self._teardown_by_reverse_topological_order(app_state)

    @contextmanager
    def _asyncio_exception_logging(self, loop: asyncio.AbstractEventLoop) -> Generator[None]:
        """Route exceptions asyncio reports on ``loop`` to a child named ``asyncio``.

        The previous handler is restored only after everything inside has exited, so
        failures during teardown are still structured.

        Args:
            loop: The running loop.

        Yields:
            Control while the handler is installed.
        """
        previous_handler = loop.get_exception_handler()
        loop.set_exception_handler(
            make_asyncio_exception_handler(
                self._log_manager.get_child_logger(_ASYNCIO_LOGGER_NAME),
            )
        )
        try:
            yield
        finally:
            loop.set_exception_handler(previous_handler)

    def _build_app_state(self) -> AppState:
        """Construct every long-lived object, in dependency order, without I/O.

        Construction does not connect, so a wiring mistake fails before any socket is
        opened. Each client and service gets its config and a child logger named after
        its class.

        Returns:
            The assembled state, with clients unopened until topological init.
        """
        self._logger.info("lifecycle.app_state.building")

        clients = AppClients(
            github=GithubClient(
                self._app_config.github_report,
                self._log_manager.get_child_logger(_GITHUB_CLIENT_LOGGER_NAME),
                github=self._github,
            ),
        )
        services = AppServices(
            github_adapter=GithubAdapter(
                clients.github,
                self._app_config.github_report,
                self._log_manager.get_child_logger(_GITHUB_ADAPTER_LOGGER_NAME),
            ),
            csv_report_writer=CsvReportWriter(
                self._app_config.github_report.REPORT_PATH,
                self._log_manager.get_child_logger(_CSV_REPORT_WRITER_LOGGER_NAME),
            ),
        )
        return AppState(
            clients=clients,
            services=services,
            log_manager=self._log_manager,
        )

    async def _init_by_topological_order(self, app_state: AppState) -> None:
        """Open every resource that needs an event loop, dependencies first.

        Await each client's ``start()`` in ``AppClients`` field order.

        Args:
            app_state: The state whose clients are being opened.
        """
        self._logger.info("lifecycle.resources.initializing")
        await app_state.clients.github.start()

    async def _teardown_by_reverse_topological_order(self, app_state: AppState) -> None:
        """Release every resource, in the exact reverse of the startup order.

        A resource is closed only once everything that might still call it is gone. Give
        each client's ``stop()`` its own ``try`` / ``finally`` so one failure cannot leak
        the rest. The log manager is flushed last, since everything else logs through it.

        Args:
            app_state: The state being torn down.
        """
        self._logger.info("lifecycle.resources.tearing_down")
        try:
            await app_state.clients.github.stop()
        finally:
            app_state.log_manager.flush()
