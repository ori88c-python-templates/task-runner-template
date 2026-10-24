"""Rewrite a stdlib ``LogRecord`` through a closed-over child logger."""

import logging
from typing import Final

from structlog.typing import FilteringBoundLogger

_STDLIB_LOGGER_KEY: Final = "stdlib_logger"
_STRUCTLOG_LEVELS: Final = (logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO)


def _structlog_level(levelno: int) -> int:
    """Round ``levelno`` down to a level structlog's ``log()`` accepts.

    structlog only knows the five canonical levels, so a library-defined level (a TRACE
    of 5, a NOTICE of 25) maps to the canonical level below it, or ``DEBUG``.

    Args:
        levelno: ``LogRecord.levelno``.

    Returns:
        One of ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, ``CRITICAL``.
    """
    return next((level for level in _STRUCTLOG_LEVELS if levelno >= level), logging.DEBUG)


class StdlibLogHandler(logging.Handler):
    """Forward records from stdlib ``logging`` (third-party SDKs) as structured JSON."""

    def __init__(self, logger: FilteringBoundLogger) -> None:
        """Keep the child logger this handler emits through.

        Args:
            logger: Child named ``stdlib``. Closed over so this package does not
                reach for a global ``LogManager``.
        """
        super().__init__()
        self._logger: Final = logger

    def emit(self, record: logging.LogRecord) -> None:
        """Forward ``record`` at the matching structlog level.

        The event string is the library's own sentence (``record.getMessage()``), not
        a dotted app event. Which library said it is kept in ``stdlib_logger``, since
        every bridged record shares the one ``stdlib`` context.

        Args:
            record: A record from any stdlib logger that propagated to the root.
        """
        try:
            extra: dict[str, object] = {_STDLIB_LOGGER_KEY: record.name}
            if record.exc_info:
                extra["exc_info"] = record.exc_info
            self._logger.log(_structlog_level(record.levelno), record.getMessage(), **extra)
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)
