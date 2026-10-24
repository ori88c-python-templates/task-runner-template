# config

Pydantic models describing the application's configuration, and immutable identity
constants that must not be overridden by the environment.

Nothing else belongs here: no clients, no I/O, no reading of `os.environ` outside the
settings machinery.

Callers outside this package import from [`__init__.py`](__init__.py):
`from app.config import AppConfig, LoggerConfig, APP_NAME`. `AppConfig` still
composes sibling modules by their module path; it must not import `from app.config
import …`.

## Table of Contents

- [Shape](#shape)
- [Conventions](#conventions)
- [Validation](#validation)
- [Adding a resource](#adding-a-resource)

## Shape

`AppConfig` is the root. It is a composition of one model per resource, so each resource owns its
own validation and can be constructed on its own in a test:

```
AppConfig
├── ENV                       Environment: local | dev | staging | prod
├── logger        LoggerConfig        MIN_LOG_LEVEL
└── github_report GithubReportConfig  ORG_URL, REPOS_LIMIT, TOKEN, REQUEST_TIMEOUT_SECONDS,
                                      OUTPUT_DIR_PATH
                                      ORG_NAME is derived from ORG_URL
                                      REPORT_PATH is the dated CSV under OUTPUT_DIR_PATH
```

### Identity constants

[`app_consts.py`](app_consts.py) holds the log `app` identity (`APP_NAME`). It is a contract with
observability, not a deployment setting: a typo in `.env` would silently detach every log line from
its dashboards and alerts.

## Conventions

- Field names are `ALL_CAPS` so they read the same in code as they do in the environment.
- A duration, timeout, or TTL is an `int` whose name ends in `_SECONDS` or `_MS` for the unit
  the downstream API actually takes (`GITHUB_REPORT__REQUEST_TIMEOUT_SECONDS`). Do not use
  `timedelta`, and do not convert under the hood (no seconds-to-ms multiply).
- Only `AppConfig` inherits from `BaseSettings`; the resource models are plain `BaseModel`s.
- Environment variables follow the nested model path, joined by `__`, so
  `AppConfig.logger.MIN_LOG_LEVEL` comes from `LOGGER__MIN_LOG_LEVEL`. Matching is
  case-insensitive.
- Unknown keys are rejected, including in `.env`, so a typo or a stale variable fails at startup
  instead of being silently ignored.
- Secrets are `SecretStr`, which keeps them out of reprs and `model_dump()`.
- Derived values are `@property`s, not `computed_field`s, so they are not serialised with the
  model. `ORG_NAME` is the login from `ORG_URL`. `REPORT_PATH` is the dated CSV under
  `OUTPUT_DIR_PATH`. A path is checked for shape, not for whether the directory exists.

## Validation

Configuration is validated once, at construction, so a bad deployment fails at startup instead of
at first use. Prefer Pydantic's built-in constraints over hand-written checks:

- Range and length constraints via `Field(ge=..., le=..., min_length=...)`.
- Closed sets via `StrEnum` (`Environment`, `LogLevel`) or `Literal`.
- Rules that span more than one field or model via `@model_validator(mode="after")`. `AppConfig`
  uses one to reject settings that are individually legal but wrong for production, such as
  `LOGGER__MIN_LOG_LEVEL=debug` when `ENV=prod`.

## Adding a resource

1. Add `<resource>_config.py` with a `BaseModel` holding only the settings that genuinely vary
   between deployments. Anything the client library already defaults well should stay defaulted.
2. Add the field to `AppConfig`. Omit a default if the resource is mandatory.
3. Re-export it from [`__init__.py`](__init__.py).
4. Document the new variables in `.env.example`.
