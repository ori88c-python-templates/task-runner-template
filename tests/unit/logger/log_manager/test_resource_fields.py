"""Process identity fields stamped on every LogManager record."""

import socket
from io import BytesIO

from app.config import APP_NAME, Environment, LoggerConfig, LogLevel
from app.logger.log_manager import LogManager
from tests.log_records import read_records


def test_every_record_carries_resource_fields(sink: BytesIO) -> None:
    """env, app, instance, and app.version are present with their gold-standard values."""
    log = LogManager(
        LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
        env=Environment.STAGING,
        app_version="9.9.9",
        stream=sink,
    ).get_child_logger("UsersService")

    log.info("user.created")

    (record,) = read_records(sink)
    assert record["env"] == Environment.STAGING.value
    assert record["app"] == APP_NAME
    assert record["instance"] == socket.gethostname()
    assert record["app.version"] == "9.9.9"


def test_two_managers_do_not_share_env(sink: BytesIO) -> None:
    """A second manager's env does not leak into the first manager's records."""
    other_sink = BytesIO()
    first = LogManager(
        LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
        env=Environment.DEV,
        app_version="0.1.0",
        stream=sink,
    )
    second = LogManager(
        LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
        env=Environment.PROD,
        app_version="0.1.0",
        stream=other_sink,
    )

    first.get_child_logger("First").info("first.event")
    second.get_child_logger("Second").info("second.event")

    (first_record,) = read_records(sink)
    (second_record,) = read_records(other_sink)
    assert first_record["env"] == Environment.DEV.value
    assert second_record["env"] == Environment.PROD.value
