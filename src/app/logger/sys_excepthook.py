"""Log uncaught process exceptions as structured JSON."""

import sys
from collections.abc import Callable
from types import TracebackType
from typing import Final

from structlog.typing import FilteringBoundLogger

_UNHANDLED_PROCESS_EVENT: Final = "process.unhandled_exception"

type Excepthook = Callable[[type[BaseException], BaseException, TracebackType | None], None]


def make_sys_excepthook(
    logger: FilteringBoundLogger,
    fallback: Excepthook = sys.__excepthook__,
) -> Excepthook:
    """Build a ``sys.excepthook`` that logs through ``logger``.

    Args:
        logger: Child logger named ``sys.excepthook``.
        fallback: Called for ``KeyboardInterrupt`` and ``SystemExit`` so the
            interpreter still exits the usual way. Defaults to the original hook.

    Returns:
        A callable assignable to ``sys.excepthook``.
    """

    def handle_uncaught_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        """Log ``exc_value`` unless it is an interrupt or an intentional exit.

        Args:
            exc_type: The exception class.
            exc_value: The raised instance.
            exc_traceback: Traceback, or ``None`` when one was never collected.
        """
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            fallback(exc_type, exc_value, exc_traceback)
            return
        logger.error(
            _UNHANDLED_PROCESS_EVENT,
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    return handle_uncaught_exception
