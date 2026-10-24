# unit

In-process tests only. Conventions are in [.cursor/rules/tests.mdc](../../.cursor/rules/tests.mdc).

## Table of Contents

- [Belongs here](#belongs-here)
- [Does not belong here](#does-not-belong-here)

## Belongs here

Layout mirrors `src/app/`: one directory per package, then one directory per component
under test, then one file per feature.

```
config/          app_config, github_report_config
clients/         github/github_client (start, stop, search, authorization)
services/        github/github_adapter, report/csv_report_writer
lifecycle/       lifecycle_manager (task runner, teardown, CSV file, asyncio handler, SIGTERM)
task_runner/     task_runner (adapter then writer, log bracketing)
logger/          log_manager, asyncio_exception_handler, sys_excepthook,
                 stdlib_log_handler, stdlib_log_bridge
distribution/    installed_app_version
```

Records written to a `sink` are read back with [`../log_records.py`](../log_records.py).
Configuration comes from [`../load_app_config.py`](../load_app_config.py). GitHub responses
come from [`../fake_github_search.py`](../fake_github_search.py).

## Does not belong here

A unit test never opens a socket, never talks to a real store, and never starts Docker.
