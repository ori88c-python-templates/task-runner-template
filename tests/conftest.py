"""Fixtures and collection hooks shared by unit, integration, and e2e tests.

``sink`` and ``log_manager`` are always available. Tests under ``integration/`` and
``e2e/`` are marked with their tree's name, so ``-m`` can select or skip them.
"""

from io import BytesIO
from pathlib import Path
from typing import Final

import pytest

from app.config import Environment, LoggerConfig
from app.logger import LogManager

_TESTS_ROOT: Final = Path(__file__).resolve().parent
_MARKED_TREES: Final = frozenset({"integration", "e2e"})


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test under ``integration/`` or ``e2e/`` with that tree's name.

    Args:
        items: The collected session. Tests outside those trees are left unmarked.
    """
    for item in items:
        if not item.path.is_relative_to(_TESTS_ROOT):
            continue
        tree = item.path.relative_to(_TESTS_ROOT).parts[0]
        if tree in _MARKED_TREES:
            item.add_marker(tree)


@pytest.fixture
def sink() -> BytesIO:
    """Provide an in-memory binary stream standing in for stdout.

    Returns:
        An empty buffer that a :class:`LogManager` can write records to.
    """
    return BytesIO()


@pytest.fixture
def log_manager(sink: BytesIO) -> LogManager:
    """Provide a LogManager that writes to ``sink``.

    Args:
        sink: Buffer every record is written to. Tests that inspect logs request
            this fixture; tests that do not can ignore it.

    Returns:
        A manager whose records tests can ignore or inspect without touching stdout.
    """
    return LogManager(
        LoggerConfig(),
        env=Environment.DEV,
        app_version="0.1.0",
        stream=sink,
    )
