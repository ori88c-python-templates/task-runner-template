# task_runner

The orchestrator of one run. `TaskRunner.run()` is what `main.py` awaits; everything the run does
starts here.

## Table of Contents

- [Belongs here](#belongs-here)
- [Does not belong here](#does-not-belong-here)
- [Why a layer of its own](#why-a-layer-of-its-own)

## Belongs here

- `TaskRunner`, constructed by `LifecycleManager.create_task_runner()` with the started
  `AppServices` and a child logger. Callers import `from app.task_runner import TaskRunner`.
- The order of the workflow: which service runs first, which result feeds the next step, and
  which steps run concurrently.

```python
async def run(self) -> None:
    self._logger.info("task_runner.run.started")
    repos = await self._services.github_adapter.get_popular_repos()
    await self._services.csv_report_writer.write(repos)
    self._logger.info("task_runner.run.completed", repos=len(repos))
```

## Does not belong here

- The work of a step. Data transformation, validation, retries, loops over records, and I/O
  belong in a service, where they are unit-tested on their own. If `run()` grows branches, a
  service is missing.
- Clients. `TaskRunner` receives `AppServices` only, so it cannot reach past a service to a client.
- Constructing anything. `LifecycleManager` builds the services and this runner.

## Why a layer of its own

`TaskRunner` takes `AppServices`, which lives in [`state/`](../state/README.md), so it has to sit
above that package and cannot live in `services/`. Sitting directly below `lifecycle/` also makes
the split structural: `uv run lint-imports` fails if a service imports the runner, so services stay
independent steps the orchestrator composes.
