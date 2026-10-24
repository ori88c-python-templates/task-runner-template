# lifecycle

The composition root. This is the only place that constructs dependencies and wires them to each
other, and the only place that knows the order resources must start and stop in.

## Table of Contents

- [Belongs here](#belongs-here)
- [Does not belong here](#does-not-belong-here)
- [Why a composition root](#why-a-composition-root)
- [The run context](#the-run-context)
- [Ordering](#ordering)
- [SIGTERM](#sigterm)

## Belongs here

- `LifecycleManager`, which builds, starts, and tears down the application state and yields the
  `TaskRunner` on top of it (`create_task_runner`), and installs process-wide logging
  (`install_process_logging`: `sys.excepthook` and the stdlib logging bridge). Callers import
  `from app.lifecycle import LifecycleManager`.
- `cancel_on_sigterm`, which turns SIGTERM into cancellation of the running task for the
  lifetime of the context.

## Does not belong here

- Business logic, or anything that reads configuration from the environment.
  `LifecycleManager` is constructed with an already-validated `AppConfig`; it never builds one.

## Why a composition root

Every component declares its dependencies in its `__init__` and receives them. Something has to
actually construct that graph, and concentrating it in one place is what keeps it out of everywhere
else. Nothing outside this package calls a constructor for a client, a service, the `TaskRunner`, or
a logger, which is what makes the rest of the codebase free of global state and testable without
patching.

`LifecycleManager` is a class rather than a set of functions because every construction step wants
the same two things, the configuration and a logger.

## The run context

How `main.py` drives this package, and the exit code of each outcome, are in the root README's
[Lifecycle](../../../README.md#lifecycle) section.

On entry, `create_task_runner` builds `AppState` (no I/O), scopes the asyncio exception handler
and the SIGTERM handler to the block, opens every client, and only then builds the `TaskRunner`
with `AppState.services` and its own child logger. `AppState` itself never leaves this package. On
exit it tears everything down, then restores both handlers. Teardown runs however the block ends:
a normal exit, an exception from the run, a failure partway through startup, Ctrl+C, or SIGTERM.

`install_process_logging` stays outside the context on purpose. An exception that escapes the
task reaches `sys.excepthook` only after the context has exited, so the hook must outlive it, and
tests that only enter the context never replace process hooks.

## Ordering

Startup runs in topological order: a resource is opened only after everything it depends on is.
Shutdown runs the exact reverse, so a resource is closed only once everything that might still call
it is gone. Declare fields in `AppClients` in that same order, so the code reads as the contract.

Startup sits inside the same `try` as the run, so a client that fails to start still triggers
teardown of the ones that did. Every client's `stop()` must therefore be safe when its `start()`
never ran or failed. Give each `stop()` its own `try` / `finally` in
`_teardown_by_reverse_topological_order`, so one failure does not leak the rest. The demo starts
`GithubClient` (rate-limit probe) on the way in and stops it in teardown after the run returns.

The log manager is flushed last. Everything else logs through it, so draining it earlier would
discard the records written during the rest of the shutdown.

## SIGTERM

Python's default SIGTERM disposition kills the process without running `finally` blocks.
Kubernetes sends SIGTERM to evict a Job's Pod, and `docker stop` sends it too, so without handling
every client would be left open.

`cancel_on_sigterm` applies the pattern `asyncio.run` already uses for Ctrl+C. The first SIGTERM
cancels the task, so `CancelledError` unwinds through teardown like any other exception, and the
process then exits with `143` (`128 + SIGTERM`). The handler puts the previous disposition back as
it fires, so a second SIGTERM kills a teardown that hangs, just as a second Ctrl+C does. Kubernetes
sends `SIGKILL` once `terminationGracePeriodSeconds` expires either way.
