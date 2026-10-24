"""The shape of the JSON records a LogManager emits."""

import io
import re
from datetime import UTC, datetime, timedelta

import pytest
import structlog

from tests.log_records import read_records
from tests.unit.logger.log_manager.helpers import ManagerFactory

ISO_8601_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def test_each_record_is_one_json_object_on_its_own_line(
    make_manager: ManagerFactory, sink: io.BytesIO
) -> None:
    """Log aggregators split on newlines, so a record must never wrap."""
    log = make_manager().get_child_logger("UsersService")

    log.info("first")
    log.info("second")
    log.info("third")

    lines = sink.getvalue().decode("utf-8").splitlines()
    assert len(lines) == 3
    assert len(read_records(sink)) == 3


def test_a_bare_call_emits_exactly_the_expected_keys(
    make_manager: ManagerFactory, sink: io.BytesIO
) -> None:
    """No stray keys leak out of the processor chain."""
    make_manager().get_child_logger("UsersService").info("user.created")

    (record,) = read_records(sink)
    assert set(record) == {
        "ts",
        "msg",
        "level",
        "context",
        "env",
        "app",
        "instance",
        "app.version",
    }


def test_structlog_default_key_names_are_renamed(
    make_manager: ManagerFactory, sink: io.BytesIO
) -> None:
    """``event`` becomes ``msg`` and ``timestamp`` becomes ``ts``."""
    make_manager().get_child_logger("UsersService").info("user.created")

    (record,) = read_records(sink)
    assert record["msg"] == "user.created"
    assert "event" not in record
    assert "timestamp" not in record


def test_context_key_holds_the_child_logger_name(
    make_manager: ManagerFactory, sink: io.BytesIO
) -> None:
    """The name given to ``get_child_logger`` identifies the emitting component."""
    make_manager().get_child_logger("GithubAdapter").info("github_adapter.popular_repos.fetched")

    (record,) = read_records(sink)
    assert record["context"] == "GithubAdapter"


def test_keyword_arguments_become_top_level_fields(
    make_manager: ManagerFactory, sink: io.BytesIO
) -> None:
    """Structured data stays queryable instead of being baked into the message."""
    log = make_manager().get_child_logger("UsersService").bind(request_id="abc-123")

    log.info("user.created", user_id=42, active=True, score=1.5, tags=["a", "b"])

    (record,) = read_records(sink)
    assert record["request_id"] == "abc-123"
    assert record["user_id"] == 42
    assert record["active"] is True
    assert record["score"] == 1.5
    assert record["tags"] == ["a", "b"]


def test_timestamp_is_iso_8601_utc_with_a_z_suffix(
    make_manager: ManagerFactory, sink: io.BytesIO
) -> None:
    """The format Datadog, ELK and Cloud Logging all parse without a custom rule."""
    before = datetime.now(UTC)
    make_manager().get_child_logger("UsersService").info("user.created")

    (record,) = read_records(sink)
    assert ISO_8601_UTC.match(record["ts"]), record["ts"]

    parsed = datetime.fromisoformat(record["ts"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
    assert timedelta(0) <= parsed - before < timedelta(seconds=10)


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("debug", "debug"),
        ("info", "info"),
        ("warning", "warning"),
        ("error", "error"),
        ("critical", "critical"),
    ],
)
def test_level_field_matches_the_method_called(
    make_manager: ManagerFactory, sink: io.BytesIO, method: str, expected: str
) -> None:
    """Every level surfaces under its canonical name."""
    log = make_manager().get_child_logger("UsersService")

    getattr(log, method)("some.event")

    (record,) = read_records(sink)
    assert record["level"] == expected


def test_exception_call_attaches_the_traceback(
    make_manager: ManagerFactory, sink: io.BytesIO
) -> None:
    """``.exception()`` inside an except block records what actually went wrong."""
    log = make_manager().get_child_logger("UsersService")

    try:
        raise RuntimeError("boom")
    except RuntimeError:
        log.exception("user.create.failed")

    (record,) = read_records(sink)
    assert record["level"] == "error"
    assert "RuntimeError: boom" in record["exception"]
    assert "Traceback" in record["exception"]


def test_contextvars_are_merged_into_records(
    make_manager: ManagerFactory, sink: io.BytesIO
) -> None:
    """Request-scoped context reaches records without being threaded through calls."""
    log = make_manager().get_child_logger("UsersService")
    structlog.contextvars.bind_contextvars(request_id="req-7")
    try:
        log.info("user.created")
    finally:
        structlog.contextvars.clear_contextvars()

    (record,) = read_records(sink)
    assert record["request_id"] == "req-7"


def test_child_loggers_do_not_share_bound_context(
    make_manager: ManagerFactory, sink: io.BytesIO
) -> None:
    """Binding to one component's logger must not bleed into another's."""
    manager = make_manager()
    users = manager.get_child_logger("UsersService").bind(tenant="acme")
    github = manager.get_child_logger("GithubAdapter")

    users.info("user.created")
    github.info("github_adapter.popular_repos.fetched")

    users_record, github_record = read_records(sink)
    assert users_record["tenant"] == "acme"
    assert "tenant" not in github_record
    assert github_record["context"] == "GithubAdapter"


def test_empty_child_logger_name_is_rejected(make_manager: ManagerFactory) -> None:
    """An unnamed logger produces records nothing can be traced back to."""
    with pytest.raises(ValueError, match="name"):
        make_manager().get_child_logger("")
