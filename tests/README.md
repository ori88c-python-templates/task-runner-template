# tests

The test suite, split by how much of the real world a test is allowed to touch.

## Table of Contents

- [Layout](#layout)
- [Running](#running)

## Layout

| Path | What belongs there |
| --- | --- |
| [`unit/`](unit/README.md) | In-process tests. Dependencies are injected (buffers, temp files, `AsyncMock`, `httpx.MockTransport`). |
| [`integration/`](integration/README.md) | A client or service against a real store or API. Needs a network. |
| [`e2e/`](e2e/README.md) | The whole process, from `main` to its exit code. Needs a network. |

Within each tree, layout mirrors `src/app/`: one directory per package, then one
directory per component under test, then one file per feature.

## Running

```bash
uv run pytest
uv run pytest -v
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/e2e
```

`testpaths` in `pyproject.toml` lists `tests/unit`, then `tests/integration`, then `tests/e2e`, so a
bare `uv run pytest` collects in that order. Unit tests are offline. Integration and e2e call
GitHub and use `GITHUB_REPORT__TOKEN` when it is set.

Conventions are defined in [.cursor/rules/tests.mdc](../.cursor/rules/tests.mdc).
