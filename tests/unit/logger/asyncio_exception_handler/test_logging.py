"""The asyncio hook logs through a LogManager child named ``asyncio``."""

import asyncio
from io import BytesIO

from app.logger import LogManager, make_asyncio_exception_handler
from tests.log_records import read_records


def test_exception_in_context_is_logged(log_manager: LogManager, sink: BytesIO) -> None:
    """An ``exception`` key becomes ``asyncio.unhandled_exception`` with a traceback."""
    handler = make_asyncio_exception_handler(log_manager.get_child_logger("asyncio"))
    loop = asyncio.new_event_loop()
    try:
        handler(loop, {"exception": RuntimeError("boom")})
    finally:
        loop.close()

    (record,) = read_records(sink)
    assert record["context"] == "asyncio"
    assert record["msg"] == "asyncio.unhandled_exception"
    assert record["level"] == "error"
    assert "RuntimeError: boom" in record["exception"]


def test_message_without_exception_is_logged(log_manager: LogManager, sink: BytesIO) -> None:
    """An asyncio ``message`` string is still a structured record."""
    handler = make_asyncio_exception_handler(log_manager.get_child_logger("asyncio"))
    loop = asyncio.new_event_loop()
    try:
        handler(loop, {"message": "Task exception was never retrieved"})
    finally:
        loop.close()

    (record,) = read_records(sink)
    assert record["context"] == "asyncio"
    assert record["msg"] == "asyncio.unhandled_exception"
    assert record["asyncio_message"] == "Task exception was never retrieved"
    assert "exception" not in record
