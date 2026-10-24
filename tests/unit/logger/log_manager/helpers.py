"""Shared types for the :class:`LogManager` tests.

Kept separate from ``conftest.py`` because fixtures are discovered by pytest while these are
imported by name, and importing from a conftest module is discouraged.
"""

from collections.abc import Callable

from app.logger.log_manager import LogManager

ManagerFactory = Callable[..., LogManager]
