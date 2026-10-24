# models

Shared models: the domain objects and payload schemas that the `TaskRunner`, services,
and clients pass between each other.

## Table of Contents

- [Belongs here](#belongs-here)
- [Does not belong here](#does-not-belong-here)
- [Conventions](#conventions)

## Belongs here

- Domain models that more than one component uses. The demo's
  [`GithubRepoInfo`](github/github_repo_info.py) is a `NamedTuple`: an immutable record the
  adapter produces and the writer consumes. The values are already validated by the SDK, so
  there is nothing for Pydantic to check.
- Payloads exchanged with external APIs, queues, and SDKs, once parsed — use a Pydantic model
  when the payload needs validation, defaults, or aliases.
- Enums and value objects those models are built from.

## Does not belong here

- Configuration models — those live in [`config/`](../config/README.md).
- Storage schemas. Keep them separate from the domain models, so a column rename is not
  automatically a change to every service.
- Anything that performs I/O. Models are data plus validation, nothing else.

## Conventions

- One concept per file, named after the concept in `snake_case`.
- Grouped into a subdirectory per domain, named after that domain, rather than left flat. Nesting
  does not shorten the filename: `github/github_repo_info.py`. Each domain package re-exports its
  models from `__init__.py`, so callers write `from app.models.github import GithubRepoInfo`
  rather than the leaf path. `app.models` re-exports what other packages import.
- Field names are `snake_case`. The `ALL_CAPS` convention is specific to config models, where the
  names double as environment variable names.
- Prefer a `NamedTuple` (or a frozen dataclass) for an immutable record that does not validate.
  Prefer Pydantic when inbound data needs constraints. Put validation in the model rather than
  in the caller, and prefer Pydantic's built-in constraints over hand-written checks.
