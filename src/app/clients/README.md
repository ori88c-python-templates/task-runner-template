# clients

Clients for external resources: the application's data access layer.

## Table of Contents

- [Belongs here](#belongs-here)
- [Does not belong here](#does-not-belong-here)
- [Dependency injection](#dependency-injection)
- [Lifecycle contract](#lifecycle-contract)

## Belongs here

- One client class per resource, in a subdirectory named after that resource:
  `clients/github/github_client.py`.
- Connection pools, query helpers, and the thin wrappers around databases, queues, and
  third-party SDKs. The demo's `GithubClient` owns a `githubkit.GitHub` instance, probes
  `/rate_limit` on `start()`, and searches repositories by stars.

Callers outside this package import from [`__init__.py`](__init__.py):
`from app.clients import GithubClient`. Modules inside a client package still import
siblings by module path.

## Does not belong here

- Business logic. A client executes a command against one resource; it does not decide whether
  that command should run. That belongs in a service.
- Configuration loading. A client is constructed with an already-validated config model; it never
  reads the environment.
- Schema changes. A client does not create tables or run migrations.

## Dependency injection

A client declares its config and a child logger in its `__init__`. The composition root constructs
it once, starts it in topological order, and stores it on `AppClients`. A client never constructs
another client, reaches for a global, or builds its own logger.

## Lifecycle contract

- `__init__` does no I/O. Construction happens before any client is started, so a wiring
  mistake fails before a socket is opened.
- `async def start()` opens the connection and proves it works (for example a ping). A failure
  raises; the run then fails at startup rather than at first use.
- `async def stop()` releases the connection. It must be safe when `start()` never ran or failed,
  because a failed startup still tears down every client.
