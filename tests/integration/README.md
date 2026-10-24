# integration

Tests that exercise a client or service against a real external store or API.

The first case is [`clients/github/github_client/test_search.py`](clients/github/github_client/test_search.py):
`GithubClient` against the live GitHub Search API. It needs a network. A
`GITHUB_REPORT__TOKEN` in the environment is used when present (CI sets it from
`secrets.GITHUB_TOKEN`).

## Table of Contents

- [Belongs here](#belongs-here)
- [Does not belong here](#does-not-belong-here)

## Belongs here

A client or service constructed with real credentials, pointed at a real API or at throwaway
infrastructure started once for the session. When a store lands, add
[Testcontainers](https://testcontainers-python.readthedocs.io/) as a dev dependency and expose
the container's config as a session fixture in [`../conftest.py`](../conftest.py), so later
tests reuse it rather than starting another container. Tests that need Docker skip when the
daemon is unreachable.

The root [`../conftest.py`](../conftest.py) marks every test collected under this tree as
`integration`.

## Does not belong here

This is not the whole process. `main`, `LifecycleManager`, and exit codes belong in
[`../e2e/`](../e2e/README.md). In-process tests (buffers, temp files, `AsyncMock`, mock
transports) belong in [`../unit/`](../unit/README.md).
