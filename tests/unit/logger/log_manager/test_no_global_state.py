"""The executable form of the no-global-logger rule.

If any of these fail, someone has reintroduced process-wide logging configuration and
the ordering and testability guarantees the rest of the codebase relies on are gone.
"""

import io

import structlog

from tests.log_records import read_records
from tests.unit.logger.log_manager.helpers import ManagerFactory


def test_building_a_manager_does_not_configure_structlog(
    make_manager: ManagerFactory,
) -> None:
    """``LogManager`` must never call ``structlog.configure()``."""
    assert not structlog.is_configured()

    make_manager().get_child_logger("UsersService").info("user.created")

    assert not structlog.is_configured()


def test_manager_does_not_mutate_structlog_defaults(
    make_manager: ManagerFactory,
) -> None:
    """The global default processor chain and logger factory stay untouched."""
    before = structlog.get_config().copy()

    make_manager().get_child_logger("UsersService").info("user.created")

    after = structlog.get_config()
    assert after["processors"] == before["processors"]
    assert after["logger_factory"] is before["logger_factory"]
    assert after["wrapper_class"] is before["wrapper_class"]


def test_manager_output_is_unaffected_by_structlog_global_config(
    make_manager: ManagerFactory, sink: io.BytesIO
) -> None:
    """Even a hostile global configuration cannot change what a manager emits.

    ``structlog.configure()`` is reset afterwards so this test cannot leak into others.
    """
    structlog.configure(
        processors=[structlog.processors.KeyValueRenderer()],
        logger_factory=structlog.PrintLoggerFactory(),
    )
    try:
        make_manager().get_child_logger("UsersService").info("user.created")

        (record,) = read_records(sink)
        assert record["msg"] == "user.created"
        assert record["context"] == "UsersService"
    finally:
        structlog.reset_defaults()
