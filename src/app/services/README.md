# services

Business services: the application's service layer.

## Table of Contents

- [Belongs here](#belongs-here)
- [Does not belong here](#does-not-belong-here)
- [Dependency injection](#dependency-injection)

## Belongs here

- One service class per use case, in a subdirectory named after that use case:
  `services/github/github_adapter.py`, `services/report/csv_report_writer.py`. The
  basename still names the concept, so grep and tracebacks stay readable.
- Service-layer exceptions in a sibling `*_errors.py` in that same directory, not
  in the service module (`github_adapter_errors.py` holds
  `GithubOrganizationNotFoundError`). A service that grows more than one error should not
  force those types to live next to the business methods.
- The work of each step of the run: validation that spans models, coordinating clients,
  deciding what to persist. The order of the steps across services belongs to the
  [`TaskRunner`](../task_runner/README.md), not here.

Public types are re-exported from [`__init__.py`](__init__.py), so callers import
`from app.services import GithubAdapter, CsvReportWriter` rather than the nested path.
Modules inside this package still import siblings by module path; `from app.services
import …` inside a service module would cycle through that same `__init__.py`.

## Does not belong here

- Raw resource access that is not already wrapped in a client. A service calls `clients/`; it
  does not open a connection or construct an SDK client.
- Schemas — those live in [`models/`](../models/README.md).

## Dependency injection

A service declares every dependency in its `__init__`: the clients it needs and a child logger
named after itself. The composition root constructs those once and stores the service on
`AppServices`. A service never constructs a client, reaches for a global, or builds its own
logger. Per-call inputs (an id, a date range, a batch) are method arguments, not constructor
dependencies, so one instance serves the whole run.
