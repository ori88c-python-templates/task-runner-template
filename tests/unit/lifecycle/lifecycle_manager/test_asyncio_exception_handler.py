"""The asyncio hook is scoped to the context and does not leak past it."""

import asyncio
from collections.abc import AsyncGenerator
from io import BytesIO
from typing import Any

import pytest

from app.lifecycle import LifecycleManager
from tests.log_records import read_records


def previous_handler(_loop: asyncio.AbstractEventLoop, _context: dict[str, Any]) -> None:
    """Stand in for whatever handler the loop had before the run.

    Args:
        _loop: Unused; required by asyncio's contract.
        _context: Unused; required by asyncio's contract.
    """


@pytest.fixture
async def loop_with_previous_handler() -> AsyncGenerator[asyncio.AbstractEventLoop]:
    """Install ``previous_handler`` on the test's loop, then clear it.

    Yields:
        The running loop, with ``previous_handler`` as its exception handler.
    """
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(previous_handler)
    try:
        yield loop
    finally:
        loop.set_exception_handler(None)


async def test_unhandled_asyncio_error_inside_the_context_is_structured(
    lifecycle_manager: LifecycleManager,
    sink: BytesIO,
) -> None:
    """An exception reported to the loop becomes an ``asyncio`` record."""
    async with lifecycle_manager.create_task_runner():
        asyncio.get_running_loop().call_exception_handler(
            {"message": "Task exception was never retrieved", "exception": RuntimeError("boom")},
        )

    (record,) = [record for record in read_records(sink) if record["context"] == "asyncio"]
    assert record["msg"] == "asyncio.unhandled_exception"
    assert "RuntimeError: boom" in record["exception"]


async def test_previous_handler_is_restored_after_a_normal_exit(
    lifecycle_manager: LifecycleManager,
    loop_with_previous_handler: asyncio.AbstractEventLoop,
) -> None:
    """The loop gets back the handler it had before the context was entered."""
    async with lifecycle_manager.create_task_runner():
        assert loop_with_previous_handler.get_exception_handler() is not previous_handler

    assert loop_with_previous_handler.get_exception_handler() is previous_handler


async def test_previous_handler_is_restored_when_the_task_raises(
    lifecycle_manager: LifecycleManager,
    loop_with_previous_handler: asyncio.AbstractEventLoop,
) -> None:
    """A failing task does not leave the run's handler installed on the loop."""
    with pytest.raises(RuntimeError, match="boom"):
        async with lifecycle_manager.create_task_runner():
            raise RuntimeError("boom")

    assert loop_with_previous_handler.get_exception_handler() is previous_handler
