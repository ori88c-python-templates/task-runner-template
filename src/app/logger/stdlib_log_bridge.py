"""Bridge the root stdlib logger into a structured ``LogManager`` child.

Third-party SDKs log through stdlib ``logging``. Without a handler on the root, their
warnings and errors fall through to ``logging.lastResort`` and print to stderr as plain
text that no log pipeline can parse.
"""

import logging

from structlog.typing import FilteringBoundLogger

from app.logger.stdlib_log_handler import StdlibLogHandler


def install_stdlib_log_bridge(logger: FilteringBoundLogger) -> None:
    """Attach the structured handler to the root stdlib logger at ``WARNING``.

    ``WARNING`` is stdlib's own default threshold, set explicitly so the choice is
    visible: SDK ``INFO`` and ``DEBUG`` chatter (per-request lines, retries, credential
    lookups) stays out of the log stream. A library that needs more is raised on its own
    named logger, not by lowering the root.

    Args:
        logger: Child logger named ``stdlib``. Closed over by the handler.
    """
    root = logging.getLogger()
    root.addHandler(StdlibLogHandler(logger))
    root.setLevel(logging.WARNING)
