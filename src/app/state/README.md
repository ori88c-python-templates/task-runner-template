# state

Typed application state: the frozen container the composition root fills once per run.

## Table of Contents

- [Belongs here](#belongs-here)
- [Does not belong here](#does-not-belong-here)
- [Why a package of its own](#why-a-package-of-its-own)

## Belongs here

- `AppState`, `AppClients`, and `AppServices`: the frozen, slotted dataclasses
  `LifecycleManager` fills once per run. `AppServices` is what the
  [`TaskRunner`](../task_runner/README.md) receives; `AppState` and `AppClients` stay inside the
  composition root.

Callers outside this package import from [`__init__.py`](__init__.py):
`from app.state import AppServices`. Modules inside it still import siblings by module path
(`from app.state.app_state import AppState`); a module importing `from app.state import AppState`
would cycle.

## Does not belong here

- Constructing clients or services. `LifecycleManager` is the composition root; this
  package only types what that root already built.
- Business logic.

## Why a package of its own

Code that consumes the state needs its type. If `AppServices` lived in `lifecycle/`, `TaskRunner`
would have to import the composition root, which sits above every other layer: an upward import,
and a cycle once the root imports the runner back.

This package sits below `task_runner/` and above `services/`, so it can name the clients and
services without either layering violation.

Add a field per client or service. `AppClients` field order is startup order, and shutdown is
that order reversed. `AppServices` fields are not started. The demo declares `AppClients.github`
and `AppServices.github_adapter` plus `csv_report_writer`.
