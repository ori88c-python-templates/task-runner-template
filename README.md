# Task Runner Template

[![CI](https://github.com/ori88c-python-templates/task-runner-template/actions/workflows/ci.yml/badge.svg)](https://github.com/ori88c-python-templates/task-runner-template/actions/workflows/ci.yml)
[![Audit](https://github.com/ori88c-python-templates/task-runner-template/actions/workflows/audit.yml/badge.svg)](https://github.com/ori88c-python-templates/task-runner-template/actions/workflows/audit.yml)

A production-grade runner for a scoped task: architecture, production logging, and configuration out of the box, so you can **focus on the product** from the start. Such a task usually begins as a simple Python script of hundreds of lines, reading environment variables by hand, with the steps coupled together so none of them can be unit-tested alone.

For example:

- A nightly export that reads invoices from a database and uploads a report to blob storage.
- A worker that drains a message broker and calls a partner API.
- A scheduled job that pulls new vulnerability findings from a scanner and publishes them to a queue for triage.

This template is a foundation for that script, including tests and CI. It fits when the job has to open async clients, such as databases, blob storage, or message brokers.

`main.py` does not change. `LifecycleManager` composes and starts every client and service, including async init, then tears them down when the run ends. The task itself is `TaskRunner.run()`.

Based on the [FastAPI polyrepo template](https://github.com/ori88c-python-templates/fastapi-polyrepo-template). It shares that template's architecture, including its dependency-injection and zero-global-state patterns.

## Table of Contents

- [Highlights](#highlights)
- [Why this template](#why-this-template)
- [Architecture](#architecture)
- [Demo task](#demo-task)
- [Layout](#layout)
- [Lifecycle](#lifecycle)
- [Configuration](#configuration)
- [Logging](#logging)
- [Running locally](#running-locally)
- [Container image](#container-image)
- [Production deploy](#production-deploy)
- [Testing](#testing)
- [Linting and type checking](#linting-and-type-checking)
- [Pre-commit hooks](#pre-commit-hooks)
- [CI](#ci)

## Highlights

- **Dependency injection, zero global state** 🧩: Every component takes dependencies in `__init__`; `LifecycleManager` (the composition root) constructs the clients, services, loggers, and the `TaskRunner` and wires them — `main.py` only builds `AppConfig` and that manager, then awaits `task_runner.run()`. It never changes as business logic grows. No module-level config, logger, or client, so tests inject dependencies instead of monkeypatching or process-wide setup.
- **One async context for the whole run** 🔁: `async with lifecycle.create_task_runner() as task_runner:` starts every client in dependency order, yields the runner, and tears everything down in reverse order, however the block ends: success, an exception, a failed startup, Ctrl+C, or SIGTERM. A Kubernetes eviction or `docker stop` cancels the run instead of killing the process, then exits with `143`.
- **Thin orchestrator, testable steps** 🧭: `TaskRunner` only decides which services run and in which order; services do the work and clients do the I/O. Packages import downward only; `lint-imports` fails cycles and upward imports, so you can test each step without the layers above it. The included GitHub report example is built in that shape: client, adapter, CSV writer.
- **Nested Pydantic config** ⚙️: `AppConfig` composes resource-specific models. Invalid config — including an unknown key in `.env` — fails at startup, before a single client is constructed.
- **Structured JSON logging** 📡: Every line carries prod-grade fields (`app`, `instance`, `env`, `app.version`). Each component gets a named child logger with its own `context`; third-party SDK warnings from stdlib `logging` are bridged into the same JSON stream.
- **Tests from day 1** 🧪: In-process unit tests cover config, logging, the GitHub client and services, the `TaskRunner`, and the lifecycle including the SIGTERM path. Integration and e2e trees hit the real GitHub API (CI sets `GITHUB_REPORT__TOKEN` from `secrets.GITHUB_TOKEN`).
- **Cursor rules that keep the conventions** 🤖: Checked-in [`.cursor/rules`](.cursor/rules) encode layers, logging, tests, and config so AI-assisted edits copy this architecture instead of inventing a new one.
- **Production-shaped ops** 🚢: Non-root multi-stage image whose default command runs the task, and GitHub Actions CI.
- **Supply-chain hygiene** 🔒: SHA-pinned Actions, weekly Dependabot for the `uv` lockfile and GitHub Actions, and a separate `uv audit` workflow on push/PR plus a weekly schedule so a CVE published while `main` is idle still fails the Audit badge.

## Why this template

Python began as a scripting language, so it is tempting to set the design aside and get the job done. It has grown well past one-off scripts, and it still does not prescribe an architecture for a batch job or a scheduled task. Without widely shared project conventions, **tightly coupled components, module-level globals, and related
anti-patterns are common in Python codebases**, in part because SDK docs favor short examples that
build a client at import time for brevity.

The risk is sharper in AI-assisted development: each existing pattern becomes the baseline the next change copies. This template is a **starting architecture that follows best practices from the first commit**, so you can spend the remaining effort on the task itself.

The guiding constraint: nothing important is reachable through a module-level global. No global
config object, no global logger, no import-time singletons. Every component declares what it needs
in its `__init__`, and a **single composition root** (`LifecycleManager`) wires those
dependencies together. That is what makes the code testable without monkeypatching and without
import-order surprises.

## Architecture

The application is a layered stack below the composition root. Imports point downward only.

```
                         main.py               awaits TaskRunner.run() inside create_task_runner()
                            |
                       lifecycle/              composition root: builds, starts, tears down
                            |
   . . . . . . . . . . . . .|. . . . . . . . . . . . . . . . . . . .
                            v
   Orchestration       task_runner/            which services run, in which order
   . . . . . . . . . . . . .|. . . . . . . . . . . . . . . . . . . .
                            v
                       state/                  typed AppState; AppServices is what TaskRunner gets
   . . . . . . . . . . . . .|. . . . . . . . . . . . . . . . . . . .
                            v
   Service layer       services/               business logic
   . . . . . . . . . . . . .|. . . . . . . . . . . . . . . . . . . .
                            v
   Data access layer   clients/                databases, queues, external APIs, SDKs

   Imports point downward only. A client never imports a service, and never
   reads AppState.

   Cross-cutting, importable from any layer, importing none of them:
       models/     config/     logger/     distribution/
```

`TaskRunner` calls a service; a service calls a client. `TaskRunner` receives `AppServices` only,
so it cannot reach a client. A client that imports a service is the canonical violation: it creates
a cycle between the service and data access layers.

`lifecycle/` is the one package allowed to import every layer — that is what a composition root is
for. `models/`, `config/`, `logger/` and `distribution/` sit below everything so they cannot import
back up.

The import graph must stay a DAG. **Python tolerates cycles; this codebase does not**. Adding a new
top-level package fails the contract until it is placed in the hierarchy, so every insertion is
forced to declare where it sits. `uv run lint-imports` enforces both rules from `pyproject.toml`.

### Avoiding hidden cyclic dependencies

A cycle is not a style nit. Python will import `A` while `B` is still half-initialized, so
construction order becomes whoever got imported first instead of a decision the composition root
made. Tests then cannot build one dependency without dragging in the other, which is how suites
slide into monkeypatching and process-wide setup. The stack is a DAG so `LifecycleManager` can
start resources in topological order and tear them down in reverse; a cycle turns that into a race
of who exists before whom.

Import Linter only sees **directory-sized** layers: `clients/` must not import `services/`. Two
modules in the same package — `github_adapter.py` importing `csv_report_writer.py` and back —
still compile, still pass `uv run lint-imports`, and are still a cycle. That is the developer's
job.

## Demo task

The run is two components joined by one model.

`GithubAdapter.get_popular_repos()` asks GitHub for the most-starred public repositories of an
organization (Microsoft, by default) and returns `list[GithubRepoInfo]`. `TaskRunner` passes that
list to `CsvReportWriter.write()`. The adapter does not know about files, and the writer does not
know about GitHub. They agree on `GithubRepoInfo` (`name`, `stars`, `forks`, `language`). That is
the coupling to copy: one component's output is the next component's input, and the contract is a
shared model. Each side stays single-purpose, can be tested on its own, and can be replaced
without the other changing.

The CSV is written under `GITHUB_REPORT__OUTPUT_DIR_PATH` (default `github_reports`). The file
name is `YYYY_MM_DD_popular_github_repos.csv` for the UTC date, and a second run on the same date
replaces it. The other settings are in [`.env.example`](.env.example).

<details>
<summary>Example <code>github_reports/2026_10_23_popular_github_repos.csv</code></summary>

```csv
rank,name,stars,forks,language
1,vscode,194250,45512,TypeScript
2,markitdown,191815,14302,Python
3,PowerToys,139662,8620,C
4,generative-ai-for-beginners,122012,64602,Jupyter Notebook
```

Star counts move. The log from a run is under [Run](#run).

</details>

## Layout

| Path | Contents |
| --- | --- |
| `src/app/config/` | Pydantic settings and immutable identity constants |
| `src/app/lifecycle/` | The composition root: `LifecycleManager`, startup, teardown, SIGTERM |
| `src/app/task_runner/` | `TaskRunner`: orchestrates the services of one run |
| `src/app/state/` | Typed `AppState`, `AppClients`, and `AppServices` |
| `src/app/logger/` | `LogManager`, the factory for injectable structured child loggers |
| `src/app/distribution/` | Installed dist metadata for the `app` import (`app.version`) |
| `src/app/models/` | Shared models. The demo's `GithubRepoInfo` is a `NamedTuple` |
| `src/app/clients/` | Data access clients for databases, queues, external APIs, and SDKs |
| `src/app/services/` | Business services; what the `TaskRunner` calls |
| `src/app/main.py` | Process entry point |
| `Dockerfile` | Production image. The default command runs the task |

Each `src/app/` directory has its own README explaining what belongs there. The GitHub report
lives in `clients/github/`, `services/github/`, `services/report/`, and `models/github/`.

## Lifecycle

`main.py` stays this shape. The task itself is `TaskRunner.run()`.

```python
def main() -> None:
    app_config = AppConfig()
    lifecycle = LifecycleManager(app_config)
    lifecycle.install_process_logging()
    asyncio.run(_run(lifecycle))


async def _run(lifecycle: LifecycleManager) -> None:
    async with lifecycle.create_task_runner() as task_runner:
        await task_runner.run()
```

| Outcome | Exit code |
| --- | --- |
| Task returns | `0` |
| Task raises | `1` |
| SIGTERM (Kubernetes eviction, `docker stop`) | `143` |
| Ctrl+C (SIGINT) | `130` on Linux and macOS |

What gets logged, and how a second signal kills a hung teardown, is in
[src/app/lifecycle/README.md](src/app/lifecycle/README.md).

## Configuration

Configuration is a composition of resource-specific Pydantic models under a single `AppConfig`
(see [src/app/config/README.md](src/app/config/README.md)). Environment variables follow the
nested model path, joined by `__`: `AppConfig.logger.MIN_LOG_LEVEL` comes from
`LOGGER__MIN_LOG_LEVEL`. `.env.example` documents every supported variable.

Validation is strict and fails at startup rather than at first use: unknown keys are rejected,
secrets are `SecretStr`, and cross-cutting rules (such as forbidding debug logging in production)
are enforced by model validators.

## Logging

Every record is one JSON object, so the same keys can be filtered in grep or in Grafana, Datadog,
or Groundcover. There is no process-wide `structlog.configure()`;
[`LogManager`](src/app/logger/README.md) stamps identity on each record and hands out a named
child, which is what makes a test inject a logger instead of patching a global.

```json
{"context": "LifecycleManager", "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-17T00:00:00.000000Z", "msg": "lifecycle.resources.initializing"}
```

The keys on it:

- `context` — the component (`get_child_logger` name, or a bridge such as `stdlib`)
- `env` — `local` / `dev` / `staging` / `prod`
- `app` — fixed `APP_NAME`, not an env var
- `instance` — hostname of this process; in a Kubernetes Job, the Pod name, unique per run
- `app.version` — installed distribution version, injected by the composition root
- `level`, `ts` (UTC, `Z` suffix), `msg`

`LogManager` receives a `LoggerConfig` and hands out children through `get_child_logger(name)`.
Components take a logger in `__init__` and never call a global one.

An uncaught exception (`sys.excepthook`), an unhandled asyncio error, and warnings that
third-party SDKs emit through stdlib `logging` are all rewritten onto those children. `context`
values are documented in [src/app/logger/README.md](src/app/logger/README.md).

## Running locally

### Requirements

- Python 3.14 (pinned in `.python-version`; `uv` can install it)
- [uv](https://docs.astral.sh/uv/) for dependency management

### Setup

```bash
uv sync
uv run pre-commit install
cp .env.example .env
```

`uv sync` installs the dev tools. `uv run pre-commit install` registers the Git hook once per
clone so commits run the checks in [Pre-commit hooks](#pre-commit-hooks).

`.env.example` is a working local configuration, not a list of placeholders. `.env` is
git-ignored. Re-copy it when `.env.example` changes: a stale variable in `.env` is rejected at
startup.

### Run

```bash
uv run app
```

<details>
<summary>Example stdout from <code>uv run app</code> (structured JSON, one object per line)</summary>

```
{"context": "LifecycleManager", "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-23T06:13:58.033433Z", "msg": "lifecycle.task_runner.creating"}
{"context": "LifecycleManager", "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-23T06:13:58.033529Z", "msg": "lifecycle.app_state.building"}
{"context": "LifecycleManager", "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-23T06:13:58.033786Z", "msg": "lifecycle.resources.initializing"}
{"context": "GithubClient", "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-23T06:13:58.033835Z", "msg": "github.starting"}
{"context": "GithubClient", "search_remaining": 10, "core_remaining": 56, "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-23T06:13:58.164192Z", "msg": "github.started"}
{"context": "TaskRunner", "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-23T06:13:58.164299Z", "msg": "task_runner.run.started"}
{"context": "GithubClient", "org": "microsoft", "total_count": 8208, "returned": 4, "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-23T06:13:58.536685Z", "msg": "github.search.completed"}
{"context": "GithubAdapter", "org": "microsoft", "count": 4, "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-23T06:13:58.536789Z", "msg": "github_adapter.popular_repos.fetched"}
{"context": "CsvReportWriter", "path": "github_reports/2026_10_23_popular_github_repos.csv", "repos": 4, "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-23T06:13:58.538714Z", "msg": "csv_report.written"}
{"context": "TaskRunner", "repos": 4, "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-23T06:13:58.538778Z", "msg": "task_runner.run.completed"}
{"context": "LifecycleManager", "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-23T06:13:58.538824Z", "msg": "lifecycle.resources.tearing_down"}
{"context": "GithubClient", "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-23T06:13:58.538861Z", "msg": "github.stopping"}
{"context": "GithubClient", "env": "local", "app": "task-runner-template", "instance": "MacBook-Pro.local", "app.version": "1.0.0", "level": "info", "ts": "2026-10-23T06:13:58.539663Z", "msg": "github.stopped"}
```

</details>

## Container image

The [Dockerfile](Dockerfile) is a production-style image (multi-stage, non-root, frozen lockfile,
no `.env`). The virtualenv is owned by root; the runtime user cannot rewrite it. The image
creates `github_reports/` and gives that directory to the runtime user, which is where the CSV
is written. The image is not part of the default local loop.

```bash
docker build -t task-runner-template .
```

The default command runs the task once and exits:

```bash
docker run --rm --env-file .env task-runner-template
```

`CMD` is exec form, so the Python process is PID 1 and receives `docker stop`'s SIGTERM directly.

## Production deploy

This repository does not ship Helm or Kubernetes YAML. The image fits a Kubernetes `Job` or
`CronJob`: one process per Pod, one run per process. Use the exit code as the outcome — the Job
controller retries a non-zero exit up to `backoffLimit`. Keep `terminationGracePeriodSeconds`
longer than the slowest teardown, because Kubernetes sends `SIGKILL` once it expires.

## Testing

```bash
uv run pytest
```

Three trees, one invocation. Layout under each tree mirrors `src/app/`. Unit tests stay offline
(`httpx.MockTransport`). Integration and e2e call the real GitHub API and need a network; they
use `GITHUB_REPORT__TOKEN` when set. CI passes `${{ secrets.GITHUB_TOKEN }}` as that variable.

```bash
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/e2e
```

- **Unit** ([tests/unit/](tests/unit/README.md)): In-process. Dependencies are injected
  (buffers, temp files, `AsyncMock`, a mock GitHub transport). Includes `LifecycleManager`:
  teardown when the run raises, the scoped asyncio handler, and SIGTERM unwinding to exit code
  `143`. `TaskRunner` is tested on its own, without the lifecycle.
- **Integration** ([tests/integration/](tests/integration/README.md)): `GithubClient` against
  the live Search API. Needs a network.
- **End-to-end** ([tests/e2e/](tests/e2e/README.md)): `python -m app.main` in a subprocess,
  asserting on exit code, JSON lines, and the CSV file. Needs a network.

## Linting and type checking

```bash
uv run ruff format .
uv run ruff check .
uv run pyright
uv run lint-imports
```

[Ruff](https://docs.astral.sh/ruff/) both formats and lints: 100-column lines, double quotes, and a
broad rule set that includes Google-style docstring checks, import sorting, and a ban on `print`.
Formatting is the formatter's job alone — the quote and comma lint rules are deliberately left off
because they fight it.

[Pyright](https://microsoft.github.io/pyright/) runs in strict mode over `src` and `tests`.

[Import Linter](https://import-linter.readthedocs.io/) enforces the one-directional stack: an
upward import, a cycle, or a new top-level package that has not been placed in the hierarchy all
fail the contract.

All three are configured in `pyproject.toml`, and every rule exemption there carries a comment
explaining itself.

## Pre-commit hooks

The same four commands, plus `uv audit --locked --preview-features audit-command`, run on
`git commit` via [pre-commit](https://pre-commit.com/). Format in the hook is
`ruff format --check .`, so an unformatted tree fails the commit instead of rewriting it.
The audit hook needs a network to fetch advisories. A CVE published while `main` is idle
is still caught by the weekly Audit workflow, because the lock does not change when the
advisory appears.

After `uv sync`, install the hook once:

```bash
uv run pre-commit install
```

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on pushes and pull requests to `main`:
ruff, pyright, import-linter, the full pytest suite (with `GITHUB_REPORT__TOKEN` set from
`secrets.GITHUB_TOKEN` so the GitHub cases have 30 searches/min), and `docker build` with no
push. There is no deploy workflow: where an image goes in production is a product decision, not
a template one.

[`.github/workflows/audit.yml`](.github/workflows/audit.yml) runs `uv audit --locked` on those
same events and weekly, so a CVE published while `main` is idle still fails the Audit badge.
Dependabot ([`.github/dependabot.yml`](.github/dependabot.yml)) opens weekly PRs for the `uv`
lockfile and for GitHub Actions; outdated packages without a known CVE do not fail Audit.
