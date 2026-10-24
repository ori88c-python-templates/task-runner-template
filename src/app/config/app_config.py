"""The application's root configuration model."""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.github_report_config import GithubReportConfig
from app.config.logger_config import LoggerConfig, LogLevel


class Environment(StrEnum):
    """The deployment environment the process is running in.

    ``LOCAL`` is a developer machine, as distinct from ``DEV``, which is a shared
    deployed environment.
    """

    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class AppConfig(BaseSettings):
    """Root configuration, composed of one model per resource.

    Values are read from the process environment and from ``.env``. Names follow the
    nested model path, joined by ``__``: ``AppConfig.logger.MIN_LOG_LEVEL`` comes from
    ``LOGGER__MIN_LOG_LEVEL``. Matching is case-insensitive, so environment variables
    are written in upper case by convention.

    A mandatory resource is declared without a default, so a deployment that fails to
    supply it fails at startup rather than at first use.

    Attributes:
        ENV: The deployment environment.
        logger: Structured logging settings.
        github_report: Which GitHub organization to report on, and how. Optional in
            the environment; the defaults produce a working demo run.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    ENV: Environment = Environment.DEV
    logger: LoggerConfig = Field(default_factory=LoggerConfig)
    github_report: GithubReportConfig = Field(default_factory=GithubReportConfig)

    @model_validator(mode="after")
    def _enforce_production_invariants(self) -> Self:
        """Reject configurations that are individually valid but wrong for production.

        Each resource model can only validate itself. Rules that span models, such as
        "debug logging is never acceptable in production", have to live here.

        Returns:
            The validated model.

        Raises:
            ValueError: If ``ENV`` is ``prod`` and a setting is unsafe for production.
        """
        if self.ENV is not Environment.PROD:
            return self

        if self.logger.MIN_LOG_LEVEL is LogLevel.DEBUG:
            raise ValueError(
                "LOGGER__MIN_LOG_LEVEL=debug is not allowed when ENV=prod: "
                "debug logging risks writing sensitive payloads to the log stream."
            )

        return self
