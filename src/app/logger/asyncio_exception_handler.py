"""Log unhandled asyncio exceptions as structured JSON."""

import asyncio
from collections.abc import Callable
from typing import Any, Final

from structlog.typing import FilteringBoundLogger

_UNHANDLED_ASYNCIO_EVENT: Final = "asyncio.unhandled_exception"


def make_asyncio_exception_handler(
    logger: FilteringBoundLogger,
) -> Callable[[asyncio.AbstractEventLoop, dict[str, Any]], None]:
    """Build a loop exception handler that logs through ``logger``.

    Does not call ``loop.default_exception_handler``: that dumps an unstructured
    traceback to stderr, which is the duplicate this hook exists to replace.

    Args:
        logger: Child logger named ``asyncio``.

    Returns:
        A callable suitable for ``loop.set_exception_handler``.
    """

    def handle_asyncio_exception(_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        """Log an unretrieved task exception or asyncio's handler message.

        Args:
            _loop: The running event loop. Required by asyncio's contract.
            context: asyncio's exception context dict.
        """
        exc = context.get("exception")
        if isinstance(exc, BaseException):
            logger.error(_UNHANDLED_ASYNCIO_EVENT, exc_info=exc)
            return
        logger.error(
            _UNHANDLED_ASYNCIO_EVENT,
            asyncio_message=context.get("message"),
        )

    return handle_asyncio_exception
