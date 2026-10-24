"""SIGTERM unwinds the run through teardown and exits with 143.

``SystemExit`` has to be caught inside the task that raised it: a ``SystemExit``
escaping a task stops the event loop itself, which here is pytest-asyncio's.
"""

import asyncio
import signal
from io import BytesIO

import pytest

from app.lifecycle import LifecycleManager
from tests.log_records import read_messages

_SIGTERM_EXIT_CODE = 143
_FOREVER_SECONDS = 30


async def run_until_sigterm(lifecycle_manager: LifecycleManager) -> None:
    """Send this process SIGTERM from inside the run, then wait to be cancelled.

    Args:
        lifecycle_manager: The composition root whose context is held open.
    """
    async with lifecycle_manager.create_task_runner():
        signal.raise_signal(signal.SIGTERM)
        await asyncio.sleep(_FOREVER_SECONDS)


async def test_sigterm_tears_down_and_exits_with_143(
    lifecycle_manager: LifecycleManager,
    sink: BytesIO,
) -> None:
    """The awaiting task is cancelled, teardown runs, then the process code is 143."""
    with pytest.raises(SystemExit) as exit_info:
        await run_until_sigterm(lifecycle_manager)

    assert exit_info.value.code == _SIGTERM_EXIT_CODE
    assert read_messages(sink)[-4:] == [
        "lifecycle.sigterm.received",
        "lifecycle.resources.tearing_down",
        "github.stopping",
        "github.stopped",
    ]


async def test_sigterm_handler_is_restored_after_exit(
    lifecycle_manager: LifecycleManager,
) -> None:
    """Outside the context SIGTERM goes back to the disposition it had before."""
    before = signal.getsignal(signal.SIGTERM)

    async with lifecycle_manager.create_task_runner():
        assert signal.getsignal(signal.SIGTERM) != before

    assert signal.getsignal(signal.SIGTERM) == before


async def test_cancellation_not_caused_by_sigterm_propagates_unchanged(
    lifecycle_manager: LifecycleManager,
    sink: BytesIO,
) -> None:
    """Ctrl+C and other cancellations stay ``CancelledError`` and still tear down."""
    entered = asyncio.Event()

    async def run() -> None:
        """Hold the context open until cancelled."""
        async with lifecycle_manager.create_task_runner():
            entered.set()
            await asyncio.sleep(_FOREVER_SECONDS)

    run_task = asyncio.create_task(run())
    await entered.wait()
    run_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await run_task

    messages = read_messages(sink)
    assert "lifecycle.sigterm.received" not in messages
    assert messages[-3:] == [
        "lifecycle.resources.tearing_down",
        "github.stopping",
        "github.stopped",
    ]
