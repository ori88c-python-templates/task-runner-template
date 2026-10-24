# logger

Structured JSON logging built on [structlog](https://www.structlog.org/).

## Table of Contents

- [Belongs here](#belongs-here)
- [Does not belong here](#does-not-belong-here)
- [Rule](#rule)
- [Hooks and bridges](#hooks-and-bridges)
- [One instance, but not a singleton](#one-instance-but-not-a-singleton)
- [Why no `structlog.configure()`](#why-no-structlogconfigure)
- [Output](#output)
- [UTF-8](#utf-8)
- [Output stream](#output-stream)
- [Levels](#levels)

## Belongs here

- `LogManager`, which hands out named child loggers via `get_child_logger(name)`.
- The asyncio and `sys.excepthook` factories, and the stdlib bridge: `StdlibLogHandler`
  (rewrites stdlib `LogRecord`s as JSON) and `install_stdlib_log_bridge` (attaches it to the
  root logger).

Callers import `from app.logger import LogManager`.

## Does not belong here

- `LoggerConfig`. Leaf modules still import it from `app.config`, not from this
  package's `__init__.py`.

## Rule

### Injected loggers

There is no global logger, and no module-level logger instance either. A component receives its
logger as a constructor argument:

```python
class UsersService:
    def __init__(self, logger: FilteringBoundLogger) -> None:
        self._logger = logger


# in the composition root
log_manager = LogManager(config.logger, env=config.ENV, app_version=app_version)
users_service = UsersService(log_manager.get_child_logger("UsersService"))
```

### Run-scoped fields

A field that holds for a stretch of the run, such as the batch being processed, is bound once with
`structlog.contextvars.bound_contextvars` in a `with` block. The processor chain runs
`structlog.contextvars.merge_contextvars` first, so every child logger inside the block — service,
client — includes it. `env`, `app`, `instance`, and `app.version` are stamped by `LogManager` on
every record and are never passed at the call site.

This is enforced by [.cursor/rules/logging.mdc](../../../.cursor/rules/logging.mdc).

## Hooks and bridges

`structlog.configure()` is not used as a global hook. Each surface closes over a
`LogManager` child from `wrap_logger()`. Grafana filters on `context`.

### Uncaught exceptions

- `make_sys_excepthook` (`context="sys.excepthook"`) — installed from `main` via
  `LifecycleManager.install_process_logging()`. An exception that escapes the task propagates
  out of `asyncio.run` after teardown and is logged here as `process.unhandled_exception`.
  `KeyboardInterrupt` and `SystemExit` stay on the interpreter default.
- `make_asyncio_exception_handler` (`context="asyncio"`) — `loop.set_exception_handler`
  for the lifetime of `create_task_runner`, restored afterwards. Catches what asyncio reports
  itself, such as a background task whose exception was never retrieved.

### Stdlib bridge

Third-party SDKs log through stdlib `logging`. Without a handler on the root, their warnings fall
through to `logging.lastResort` and print to stderr as plain text.
`LifecycleManager.install_process_logging()` calls `install_stdlib_log_bridge`, which attaches
`StdlibLogHandler` to the root logger and sets it to `WARNING`. Every record that propagates there
is rewritten as JSON on a child with `context="stdlib"`. The event string is the library's own
sentence, not a dotted app event, and `stdlib_logger` names the library's logger:

```json
{"stdlib_logger": "botocore.credentials", "context": "stdlib", "env": "local", "app": "task-runner-template", "instance": "worker-1", "app.version": "1.0.0", "level": "warning", "ts": "2026-10-17T00:00:00.000000Z", "msg": "Refreshing temporary credentials failed during advisory refresh period."}
```

`WARNING` is stdlib's own default threshold, set explicitly so SDK `INFO` and `DEBUG` chatter
stays out of the stream. To hear more from one library, raise that library's named logger in
`install_process_logging`; never lower the root.

## One instance, but not a singleton

An application has exactly one `LogManager`. A second one would just be a second pipeline writing
to the same stream under a different configuration, which nothing wants.

That single instance is a consequence of the wiring, not something the class enforces. `LogManager`
is deliberately *not* a singleton: the singleton pattern would put it back in global state and
recreate the import-order coupling this design exists to avoid. Construct it once in the
composition root and pass it down. Tests construct as many as they need.

## Why no `structlog.configure()`

`structlog.configure()` installs process-wide defaults. That is the global state this codebase
exists to avoid: logging behaviour would depend on import order, and a test that wanted a different
configuration would have to install it globally and then undo it. `LogManager` uses
`structlog.wrap_logger()` instead, which structlog documents as the way to use it "without any
global state". Two `LogManager` instances with different minimum levels can coexist in one process
without interfering — which is what makes logging testable.

## Output

One JSON object per line, on stdout:

```json
{"user_id": 42, "env": "dev", "app": "task-runner-template", "instance": "worker-1", "app.version": "1.0.0", "context": "UsersService", "level": "info", "ts": "2026-09-05T16:11:04.812733Z", "msg": "user.created"}
```

- `ts` — ISO 8601 / RFC 3339 in UTC with a `Z` suffix, which Datadog, ELK and Cloud Logging all
  parse natively. Renamed from structlog's default `timestamp`.
- `msg` — the log message. Renamed from structlog's default `event` by `EventRenamer`, which must
  stay immediately before the renderer since earlier processors read the `event` key.
- `context` — the name passed to `get_child_logger`, i.e. the component that emitted the record.
- `level` — the canonical level name.
- `env` — `AppConfig.ENV` (`local` / `dev` / `staging` / `prod`). Passed into `LogManager`, not
  read from `LoggerConfig`.
- `app` — `APP_NAME` in [`app_consts.py`](../config/app_consts.py). Hardcoded identity; not
  overridable in `.env`.
- `instance` — `socket.gethostname()` once when the manager is constructed. In a Kubernetes Job
  that is the Pod name, unique per run and per retry.
- `app.version` — injected by the composition root from `app.distribution`
  (`installed_app_version`). Installed metadata for the dist that provides the
  `app` import (`importlib.metadata`, populated from `pyproject.toml` at
  install). Not a string parsed from the toml file at runtime. `LogManager`
  only stamps the string it is given, same as `env`.

Both renames happen once, in `LogManager._set_property_names()`.

## UTF-8

Records are encoded once, in the renderer, and written as bytes: `_serialize()` calls
`json.dumps(..., ensure_ascii=False).encode("utf-8")`, and `structlog.BytesLogger` writes the result
to a binary stream.

Encoding at the renderer rather than at the stream is what makes the output UTF-8 everywhere. A text
stream encodes using the platform's locale, which on Windows is still a legacy code page that raises
`UnicodeEncodeError` on most of Unicode. Bypassing the text layer removes that variable entirely —
`tests/unit/logger/log_manager/test_stdout.py` proves it by forcing `PYTHONIOENCODING=cp1252`
and asserting the output is still UTF-8.

The one trade-off: writing to `sys.stdout.buffer` bypasses the text layer's buffer, so log records
can appear out of order relative to plain `print()`. Do not mix the two. Product output that is
not a log line — the demo CSV — is a file under `github_reports/`, not a line on stdout. If
something is a diagnostic, log it.

## Output stream

`LogManager(config, env=..., app_version=..., stream=...)` takes the deployment
`Environment`, the installed app version, and an optional binary stream, defaulting
to `sys.stdout.buffer`. Production looks the version up once and injects it; it
passes nothing for the stream. Tests pass a `BytesIO` or an open file, which is how
the suite asserts against real bytes instead of a mocked writer.

`flush()` drains the stream. Records are already flushed as they are written, so it only matters on
graceful shutdown. It does not close the stream — `LogManager` does not own stdout.

## Levels

`LoggerConfig.MIN_LOG_LEVEL` is a `LogLevel` enum whose members are exactly structlog's canonical
level names, so the level is validated by Pydantic at startup rather than by structlog at first
use. Filtering uses `structlog.make_filtering_bound_logger`, which discards records below the
minimum level before any processor runs. Bridged stdlib records pass two thresholds: the root
logger's `WARNING`, then `MIN_LOG_LEVEL`.
