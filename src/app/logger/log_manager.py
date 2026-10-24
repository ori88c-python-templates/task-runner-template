"""Construction of named, structured child loggers without any global state."""

import json
import socket
import sys
from types import MappingProxyType
from typing import Any, BinaryIO, Final

import structlog
from structlog.processors import NAME_TO_LEVEL
from structlog.typing import EventDict, FilteringBoundLogger, Processor, WrappedLogger

from app.config import APP_NAME, Environment, LoggerConfig

_TIMESTAMP_KEY: Final = "ts"
_MESSAGE_KEY: Final = "msg"
_LOGGER_NAME_KEY: Final = "context"
_ENV_KEY: Final = "env"
_APP_KEY: Final = "app"
_INSTANCE_KEY: Final = "instance"
_APP_VERSION_KEY: Final = "app.version"


class LogManager:
    """Hands out named child loggers that all share one logging configuration.

    Built with ``structlog.wrap_logger()``, never ``structlog.configure()``, so it holds no
    global state. One per process by wiring, not a singleton: tests build as many as they
    like. Records are encoded to UTF-8 in the renderer, so output does not depend on the
    platform locale, and every record is stamped with ``env``, ``app``, ``instance`` and
    ``app.version``. The reasoning lives in ``src/app/logger/README.md``.
    """

    def __init__(
        self,
        config: LoggerConfig,
        env: Environment,
        app_version: str,
        stream: BinaryIO | None = None,
    ) -> None:
        """Build the shared logging pipeline from configuration.

        Args:
            config: Logging settings. ``MIN_LOG_LEVEL`` is already constrained to
                structlog's canonical level names by :class:`~app.config.logger_config.LogLevel`,
                so the lookup below cannot fail.
            env: Deployment environment. Bound to the ``env`` key as its string value.
            app_version: Installed distribution version. The composition root looks
                this up once and injects it; this class only stamps the string.
            stream: Binary stream to write records to. Defaults to stdout. Tests pass a
                ``BytesIO`` or an open file to capture output; production has no reason
                to pass anything.
        """
        self._stream: Final = stream if stream is not None else sys.stdout.buffer
        self._writer: Final = structlog.BytesLogger(self._stream)
        self._resource_fields: Final = MappingProxyType(
            {
                _ENV_KEY: env.value,
                _APP_KEY: APP_NAME,
                _INSTANCE_KEY: socket.gethostname(),
                _APP_VERSION_KEY: app_version,
            }
        )
        self._processors: Final = self._build_processors()
        self._wrapper_class: Final = structlog.make_filtering_bound_logger(
            NAME_TO_LEVEL[config.MIN_LOG_LEVEL.value]
        )

    def get_child_logger(self, name: str) -> FilteringBoundLogger:
        """Create a logger that tags every record it emits with ``name``.

        Args:
            name: Identifier of the component that will own the logger, for example
                ``"UsersService"``. It is bound to the ``context`` key.

        Returns:
            A bound logger sharing this manager's processors, output stream and minimum
            level. Records below the minimum level are dropped before any processor runs.

        Raises:
            ValueError: If ``name`` is empty, which would produce records nothing can be
                traced back to.
        """
        if not name:
            raise ValueError("A child logger needs a name to be traceable.")

        return structlog.wrap_logger(
            self._writer,
            processors=self._processors,
            wrapper_class=self._wrapper_class,
        ).bind(**{_LOGGER_NAME_KEY: name})

    def flush(self) -> None:
        """Flush anything still buffered in the output stream.

        Records are already flushed as they are written, so this only matters on
        graceful shutdown, where it guarantees nothing is lost to a stream the
        interpreter never gets around to draining.
        """
        self._stream.flush()

    def _add_resource_fields(
        self,
        _logger: WrappedLogger,
        _method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        """Stamp process identity onto ``event_dict``, overwriting colliding keys.

        Args:
            _logger: Unused; required by the processor protocol.
            _method_name: Unused; required by the processor protocol.
            event_dict: The record being processed.

        Returns:
            ``event_dict`` with ``env``, ``app``, ``instance``, and ``app.version`` set.
        """
        event_dict.update(self._resource_fields)
        return event_dict

    def _build_processors(self) -> tuple[Processor, ...]:
        """Assemble the processor chain applied to every record.

        Order matters: contextvars are merged first, then process identity (so a
        call-site kwarg cannot drop ``env`` / ``app`` / ``instance`` /
        ``app.version``), then exception and Unicode handling, then the key
        renames, and the renderer last.

        Returns:
            The processor chain, ending in the renderer.
        """
        return (
            structlog.contextvars.merge_contextvars,
            self._add_resource_fields,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            *self._set_property_names(),
            self._build_renderer(),
        )

    def _set_property_names(self) -> tuple[Processor, ...]:
        """Rename structlog's default keys to the ones this codebase emits.

        structlog calls the message ``event`` and the timestamp ``timestamp``; this
        codebase uses ``msg`` and ``ts``. ``EventRenamer`` must run immediately before
        the renderer, because processors ahead of it may read the ``event`` key.

        Returns:
            The timestamp and rename processors, in the order they must run.
        """
        return (
            structlog.processors.TimeStamper(fmt="iso", utc=True, key=_TIMESTAMP_KEY),
            structlog.processors.EventRenamer(to=_MESSAGE_KEY),
        )

    def _build_renderer(self) -> Processor:
        """Build the terminal processor that serialises a record to a line of JSON.

        Returns:
            A JSON renderer producing UTF-8 bytes.
        """
        return structlog.processors.JSONRenderer(serializer=self._serialize)

    @staticmethod
    def _serialize(event_dict: EventDict, **dumps_kwargs: Any) -> bytes:
        r"""Serialise a record to UTF-8 encoded JSON.

        ``ensure_ascii=False`` keeps non-ASCII characters literal instead of expanding
        them into ``\uXXXX`` escapes, and encoding here rather than at the stream is
        what makes the output independent of the platform's locale.

        Args:
            event_dict: The processed record.
            **dumps_kwargs: Extra arguments forwarded by the renderer to ``json.dumps``.

        Returns:
            The record as a UTF-8 encoded JSON object, without a trailing newline. The
            writer appends that.
        """
        return json.dumps(event_dict, ensure_ascii=False, **dumps_kwargs).encode("utf-8")
