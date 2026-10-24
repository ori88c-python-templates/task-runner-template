"""Shared fixtures for the :class:`LogManager` tests."""

from io import BytesIO

import pytest

from app.config import Environment, LoggerConfig, LogLevel
from app.logger.log_manager import LogManager
from tests.unit.logger.log_manager.helpers import ManagerFactory


@pytest.fixture
def make_manager(sink: BytesIO) -> ManagerFactory:
    """Provide a factory for managers writing to the shared ``sink``.

    Args:
        sink: The buffer every manager built by the returned factory writes to.

    Returns:
        A callable taking an optional minimum level and returning a manager. Defaults to
        ``debug`` so tests see every record unless they are specifically about filtering.
    """

    def factory(min_level: LogLevel = LogLevel.DEBUG) -> LogManager:
        return LogManager(
            LoggerConfig(MIN_LOG_LEVEL=min_level),
            env=Environment.DEV,
            app_version="0.1.0",
            stream=sink,
        )

    return factory
