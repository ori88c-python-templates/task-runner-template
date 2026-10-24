"""The real stdout path, driven through a subprocess.

Everything else in this suite injects a stream. These tests deliberately do not, so the
default ``sys.stdout.buffer`` path is exercised for real and the raw bytes a shell would
see are what gets asserted. An earlier implementation wrapped stdout in a
``TextIOWrapper``, which closed stdout when it was garbage collected; every in-process
test passed while a plain ``python app.py`` was broken. Hence the subprocess.
"""

import gc
import io
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

from app.config import Environment, LoggerConfig, LogLevel
from app.logger.log_manager import LogManager

PREAMBLE = """
import gc
import sys

from app.config import Environment, LoggerConfig, LogLevel
from app.logger.log_manager import LogManager
"""

HEBREW = "חגי תשרי"


def run_script(body: str, **env_overrides: str) -> subprocess.CompletedProcess[bytes]:
    """Run ``body`` in a fresh interpreter and capture its raw output.

    Args:
        body: Python source appended to the shared import preamble. Dedented first, so
            it can be written as an indented triple-quoted string.
        **env_overrides: Environment variables to set for the child process.

    Returns:
        The completed process, with ``stdout`` and ``stderr`` as undecoded bytes.
    """
    return subprocess.run(
        [sys.executable, "-c", PREAMBLE + textwrap.dedent(body)],
        capture_output=True,
        env={**os.environ, **env_overrides},
        timeout=60,
        check=False,
    )


def parse_stdout(result: subprocess.CompletedProcess[bytes]) -> list[dict[str, Any]]:
    """Decode a child process's stdout as newline-delimited JSON.

    Args:
        result: A completed process whose stdout holds log records.

    Returns:
        One dict per record.
    """
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    text = result.stdout.decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def test_default_stream_writes_json_records_to_stdout() -> None:
    """With no stream argument, records go to stdout in the documented shape."""
    result = run_script(
        """
        manager = LogManager(
            LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
            env=Environment.DEV,
            app_version="0.1.0",
        )
        manager.get_child_logger("UsersService").info("user.created", user_id=42)
        """
    )

    (record,) = parse_stdout(result)
    assert set(record) == {
        "ts",
        "msg",
        "level",
        "context",
        "user_id",
        "env",
        "app",
        "instance",
        "app.version",
    }
    assert record["msg"] == "user.created"
    assert record["context"] == "UsersService"


def test_stdout_receives_literal_utf8_bytes() -> None:
    """Non-ASCII reaches the pipe as UTF-8, not as escapes or replacements."""
    result = run_script(
        f"""
        manager = LogManager(
            LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
            env=Environment.DEV,
            app_version="0.1.0",
        )
        manager.get_child_logger("UsersService").info("user.created", name="{HEBREW}")
        """
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert HEBREW.encode("utf-8") in result.stdout
    assert rb"\u" not in result.stdout

    (record,) = parse_stdout(result)
    assert record["name"] == HEBREW


def test_output_stays_utf8_under_a_legacy_locale_encoding() -> None:
    """Encoding in the renderer makes the platform's text encoding irrelevant.

    Forcing cp1252, which cannot represent Hebrew, would have crashed any implementation
    that encoded at the stream instead.
    """
    result = run_script(
        f"""
        assert sys.stdout.encoding.lower().replace("-", "") == "cp1252", sys.stdout.encoding
        manager = LogManager(
            LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
            env=Environment.DEV,
            app_version="0.1.0",
        )
        manager.get_child_logger("UsersService").info("user.created", name="{HEBREW}")
        """,
        PYTHONIOENCODING="cp1252",
        PYTHONUTF8="0",
    )

    (record,) = parse_stdout(result)
    assert record["name"] == HEBREW


def test_stdout_survives_a_garbage_collected_manager() -> None:
    """Regression: dropping a LogManager must not take stdout down with it.

    A ``TextIOWrapper`` around ``sys.stdout.buffer`` closes that buffer when it is
    collected, which killed every subsequent write in the process.
    """
    result = run_script(
        """
        first = LogManager(
            LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
            env=Environment.DEV,
            app_version="0.1.0",
        )
        first.get_child_logger("First").info("first.event")

        del first
        gc.collect()

        second = LogManager(
            LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
            env=Environment.DEV,
            app_version="0.1.0",
        )
        second.get_child_logger("Second").info("second.event")

        assert not sys.stdout.buffer.closed
        print("text-layer-alive", flush=True)
        """
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert b"text-layer-alive" in result.stdout

    records = [
        json.loads(line)
        for line in result.stdout.decode("utf-8").splitlines()
        if line.startswith("{")
    ]
    assert [record["msg"] for record in records] == ["first.event", "second.event"]


def test_many_managers_can_be_created_and_dropped() -> None:
    """Churning through managers leaves stdout usable throughout."""
    result = run_script(
        """
        for index in range(25):
            manager = LogManager(
                LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
                env=Environment.DEV,
                app_version="0.1.0",
            )
            manager.get_child_logger("Churn").info("event", index=index)
            del manager
            gc.collect()
        """
    )

    records = parse_stdout(result)
    assert [record["index"] for record in records] == list(range(25))


def test_records_are_flushed_as_they_are_written() -> None:
    """A crash must not swallow records already logged.

    The child aborts without unwinding, so anything still buffered would be lost.
    """
    result = run_script(
        """
        import os

        manager = LogManager(
            LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
            env=Environment.DEV,
            app_version="0.1.0",
        )
        manager.get_child_logger("UsersService").info("before.crash")
        os._exit(3)
        """
    )

    assert result.returncode == 3
    (record,) = [
        json.loads(line)
        for line in result.stdout.decode("utf-8").splitlines()
        if line.startswith("{")
    ]
    assert record["msg"] == "before.crash"


def test_flush_leaves_the_stream_open_and_writable(tmp_path: Path) -> None:
    """``flush()`` is for graceful shutdown, so it must not end the stream."""
    path = tmp_path / "app.log"
    with path.open("wb") as handle:
        manager = LogManager(
            LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
            env=Environment.DEV,
            app_version="0.1.0",
            stream=handle,
        )
        log = manager.get_child_logger("UsersService")

        log.info("before.flush")
        manager.flush()
        assert not handle.closed

        log.info("after.flush")

    records = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
    assert [record["msg"] for record in records] == ["before.flush", "after.flush"]


def test_dropping_a_manager_does_not_close_an_injected_stream() -> None:
    """The in-process form of the regression above, for an injected sink."""
    sink = io.BytesIO()
    manager = LogManager(
        LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
        env=Environment.DEV,
        app_version="0.1.0",
        stream=sink,
    )
    manager.get_child_logger("UsersService").info("user.created")

    del manager
    gc.collect()

    assert not sink.closed
    sink.write(b"still writable\n")
