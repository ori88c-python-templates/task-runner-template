"""Turn SIGTERM into cancellation of the running task, so teardown still runs."""

import asyncio
import signal
from collections.abc import Generator
from contextlib import contextmanager
from types import FrameType
from typing import Final

from structlog.typing import FilteringBoundLogger

_SIGTERM_EXIT_CODE: Final = 128 + signal.SIGTERM


@contextmanager
def cancel_on_sigterm(
    task: asyncio.Task[object],
    logger: FilteringBoundLogger,
) -> Generator[None]:
    """Cancel ``task`` on SIGTERM so it unwinds through teardown, then exit with ``143``.

    Python's default SIGTERM kills the process without running ``finally``. This applies
    ``asyncio.run``'s own Ctrl+C pattern: the first signal cancels the task, and the default
    disposition is put back, so a second SIGTERM kills a teardown that hangs. The handler
    only schedules work on the loop; logging happens there, never mid-signal.

    Args:
        task: The task running the ``async with`` around the run.
        logger: Child logger of the composition root.

    Yields:
        Control to the caller for as long as SIGTERM should cancel ``task``.

    Raises:
        SystemExit: ``143`` when the cancellation that reached this block came from SIGTERM.
            Any other cancellation, such as Ctrl+C, propagates unchanged.
    """
    loop = task.get_loop()
    received = False

    def cancel_task() -> None:
        """Log the signal and cancel ``task``, on the loop thread."""
        nonlocal received
        received = True
        logger.warning("lifecycle.sigterm.received")
        task.cancel()

    def on_sigterm(_signum: int, _frame: FrameType | None) -> None:
        """Restore the previous disposition and hand the cancellation to the loop.

        Args:
            _signum: Unused; required by the ``signal.signal`` contract.
            _frame: Unused; required by the ``signal.signal`` contract.
        """
        signal.signal(signal.SIGTERM, previous)
        loop.call_soon_threadsafe(cancel_task)

    previous = signal.signal(signal.SIGTERM, on_sigterm)
    try:
        yield
    except asyncio.CancelledError:
        if not received:
            raise
        task.uncancel()
        raise SystemExit(_SIGTERM_EXIT_CODE) from None
    finally:
        signal.signal(signal.SIGTERM, previous)
