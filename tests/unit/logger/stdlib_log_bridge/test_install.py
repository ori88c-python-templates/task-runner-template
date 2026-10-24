"""Installing on the root stdlib logger forwards SDK warnings and drops their chatter."""

import logging
from collections.abc import Iterator
from io import BytesIO

import pytest

from app.logger import LogManager, install_stdlib_log_bridge
from tests.log_records import read_records


@pytest.fixture
def installed_bridge(log_manager: LogManager) -> Iterator[None]:
    """Install the bridge on the process root logger, then put the root back.

    Args:
        log_manager: Buffer-backed manager the bridge writes through.

    Yields:
        Control to the test while the bridge is installed.
    """
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    try:
        install_stdlib_log_bridge(log_manager.get_child_logger("stdlib"))
        yield
    finally:
        root.handlers = previous_handlers
        root.setLevel(previous_level)


@pytest.mark.usefixtures("installed_bridge")
def test_sdk_warning_reaches_the_structured_stream(sink: BytesIO) -> None:
    """A warning on any named logger propagates to the root and comes out as JSON."""
    logging.getLogger("tests.sdk.client").warning("retrying after %s", "timeout")

    (line,) = read_records(sink)
    assert line["context"] == "stdlib"
    assert line["stdlib_logger"] == "tests.sdk.client"
    assert line["level"] == "warning"
    assert line["msg"] == "retrying after timeout"


@pytest.mark.usefixtures("installed_bridge")
def test_sdk_info_is_dropped_at_the_root_threshold(sink: BytesIO) -> None:
    """The root sits at ``WARNING``, so per-call SDK chatter never reaches the stream."""
    logging.getLogger("tests.sdk.client").info("sending request")

    assert read_records(sink) == []
