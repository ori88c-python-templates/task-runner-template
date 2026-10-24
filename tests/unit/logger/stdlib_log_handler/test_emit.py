"""Forward stdlib records through a LogManager child named ``stdlib``."""

import logging
from io import BytesIO
from types import TracebackType

import pytest

from app.config import Environment, LoggerConfig, LogLevel
from app.logger import LogManager, StdlibLogHandler
from tests.log_records import read_records

type ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None]

_TRACE = 5
_NOTICE = 25


def make_record(
    level: int,
    msg: str,
    *args: object,
    name: str = "sdk.client",
    exc_info: ExcInfo | None = None,
) -> logging.LogRecord:
    """Build a record the way a library's ``logger.log(level, msg, *args)`` call would.

    Args:
        level: Stdlib ``levelno``.
        msg: Format string; ``args`` are interpolated into it lazily.
        *args: Arguments for ``msg``.
        name: Name of the stdlib logger that emitted the record.
        exc_info: Exception triple, as ``logger.exception`` would attach.

    Returns:
        A record ready for ``StdlibLogHandler.emit``.
    """
    return logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )


def test_record_is_structured_json_naming_its_stdlib_logger(
    log_manager: LogManager,
    sink: BytesIO,
) -> None:
    """A ``LogRecord`` becomes JSON with the library's sentence as ``msg``."""
    handler = StdlibLogHandler(log_manager.get_child_logger("stdlib"))

    handler.emit(
        make_record(
            logging.WARNING,
            "Refreshing credentials in %d seconds",
            30,
            name="botocore.credentials",
        ),
    )

    (line,) = read_records(sink)
    assert line["context"] == "stdlib"
    assert line["stdlib_logger"] == "botocore.credentials"
    assert line["level"] == "warning"
    assert line["msg"] == "Refreshing credentials in 30 seconds"


@pytest.mark.parametrize(
    ("levelno", "expected"),
    [(_TRACE, "debug"), (_NOTICE, "info")],
)
def test_library_defined_levels_round_down_to_a_canonical_level(
    sink: BytesIO,
    levelno: int,
    expected: str,
) -> None:
    """A level structlog does not know maps to the canonical level below it."""
    debug_manager = LogManager(
        LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
        env=Environment.DEV,
        app_version="0.1.0",
        stream=sink,
    )
    handler = StdlibLogHandler(debug_manager.get_child_logger("stdlib"))

    handler.emit(make_record(levelno, "frame sent"))

    (line,) = read_records(sink)
    assert line["level"] == expected
    assert line["msg"] == "frame sent"


def test_error_record_includes_exception(log_manager: LogManager, sink: BytesIO) -> None:
    """An ERROR record with ``exc_info`` carries the traceback in ``exception``."""
    handler = StdlibLogHandler(log_manager.get_child_logger("stdlib"))
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        record = make_record(logging.ERROR, "boom", exc_info=(type(exc), exc, exc.__traceback__))

    handler.emit(record)

    (line,) = read_records(sink)
    assert line["context"] == "stdlib"
    assert line["level"] == "error"
    assert line["msg"] == "boom"
    assert "RuntimeError: boom" in line["exception"]
    assert "Traceback" in line["exception"]
