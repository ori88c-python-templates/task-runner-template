"""The process hook logs through a LogManager child named ``sys.excepthook``."""

from io import BytesIO
from types import TracebackType

from app.logger import LogManager, make_sys_excepthook
from tests.log_records import read_records


def test_uncaught_exception_is_logged(log_manager: LogManager, sink: BytesIO) -> None:
    """A canned ``RuntimeError`` becomes ``process.unhandled_exception``."""
    hook = make_sys_excepthook(log_manager.get_child_logger("sys.excepthook"))
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        hook(type(exc), exc, exc.__traceback__)

    (record,) = read_records(sink)
    assert record["context"] == "sys.excepthook"
    assert record["msg"] == "process.unhandled_exception"
    assert record["level"] == "error"
    assert "RuntimeError: boom" in record["exception"]
    assert "Traceback" in record["exception"]


def test_keyboard_interrupt_uses_fallback(log_manager: LogManager, sink: BytesIO) -> None:
    """``KeyboardInterrupt`` is not logged; the interpreter fallback runs instead."""
    calls: list[tuple[type[BaseException], BaseException, TracebackType | None]] = []

    def fallback(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        """Record the arguments the hook forwarded.

        Args:
            exc_type: The exception class.
            exc_value: The raised instance.
            exc_traceback: Traceback, or ``None``.
        """
        calls.append((exc_type, exc_value, exc_traceback))

    hook = make_sys_excepthook(
        log_manager.get_child_logger("sys.excepthook"),
        fallback=fallback,
    )
    interrupt = KeyboardInterrupt()
    hook(KeyboardInterrupt, interrupt, None)

    assert calls == [(KeyboardInterrupt, interrupt, None)]
    assert read_records(sink) == []
