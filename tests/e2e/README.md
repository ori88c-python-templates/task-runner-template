# e2e

The whole process: `main`, `LifecycleManager`, `TaskRunner`, and the exit code.

The first case is [`main/test_run.py`](main/test_run.py): `python -m app.main` in a subprocess
from a temp cwd (so no developer `.env`), asserting exit `0`, the lifecycle JSON lines, and
the dated CSV under `github_reports/`. It needs a network. A `GITHUB_REPORT__TOKEN` in the
environment is passed through when set.

## Table of Contents

- [Belongs here](#belongs-here)
- [Does not belong here](#does-not-belong-here)

## Belongs here

Run `python -m app.main` in a subprocess with the environment the test controls, then assert on
what an operator would see: the exit code, the JSON lines, and the CSV the run wrote. A
subprocess is the point. It is the only way to exercise the process-wide hooks `main` installs
(`sys.excepthook`, the stdlib bridge, SIGTERM handling) without installing them into the test
runner.

Point the run at throwaway infrastructure the same way integration tests do, never at a
developer's `.env`.

The root [`../conftest.py`](../conftest.py) marks every test collected under this tree as `e2e`.

## Does not belong here

A single client or service against a real store belongs in
[`../integration/`](../integration/README.md). In-process tests (buffers, temp files,
`AsyncMock`) belong in [`../unit/`](../unit/README.md).
