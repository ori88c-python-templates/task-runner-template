"""Configuration for the GitHub popular-repositories report."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Self

from pydantic import BaseModel, Field, HttpUrl, SecretStr, model_validator

_GITHUB_HOST: Final = "github.com"
_CSV_SUFFIX: Final = ".csv"
_REPORT_FILENAME_SUFFIX: Final = "_popular_github_repos.csv"


class GithubReportConfig(BaseModel):
    """Which organization to report on, how many repositories, and how to reach GitHub.

    Attributes:
        ORG_URL: Browser URL of the organization, e.g. ``https://github.com/microsoft``.
            A URL rather than a bare login because that is what a human copies from the
            address bar; the login is derived by ``ORG_NAME``.
        REPOS_LIMIT: How many of the most-starred repositories to present. Capped at
            100, the Search API's page size, so the report is exactly one request. A
            report that ever needs more adds ``githubkit``'s ``paginate`` in the client.
        TOKEN: Optional personal access token. Unauthenticated search allows 10
            requests a minute, authenticated 30. Never logged.
        REQUEST_TIMEOUT_SECONDS: httpx timeout for every GitHub request. ``githubkit``
            defaults to no timeout at all, which would let a stalled connection hang the
            run forever.
        OUTPUT_DIR_PATH: Directory the CSV is written into. The dated filename is not
            part of this setting; ``REPORT_PATH`` adds it. The directory does not have
            to exist yet.
    """

    ORG_URL: HttpUrl = HttpUrl("https://github.com/microsoft")
    REPOS_LIMIT: int = Field(default=4, ge=1, le=100)
    TOKEN: SecretStr | None = None
    REQUEST_TIMEOUT_SECONDS: int = Field(default=10, ge=1)
    OUTPUT_DIR_PATH: str = "github_reports"

    @model_validator(mode="after")
    def _require_organization_url(self) -> Self:
        """Reject URLs that do not point at exactly one GitHub organization.

        Returns:
            The validated model.

        Raises:
            ValueError: If the host is not ``github.com``, or the path is not a single
                segment (``/microsoft``), such as a repository URL or the bare site root.
        """
        if self.ORG_URL.host != _GITHUB_HOST:
            raise ValueError(f"GITHUB_REPORT__ORG_URL must point at {_GITHUB_HOST}.")
        if not self._path_segments():
            raise ValueError(
                "GITHUB_REPORT__ORG_URL must name an organization, "
                f"e.g. https://{_GITHUB_HOST}/microsoft."
            )
        if len(self._path_segments()) > 1:
            raise ValueError(
                "GITHUB_REPORT__ORG_URL must be an organization URL, not a repository URL."
            )
        return self

    @model_validator(mode="after")
    def _require_output_directory(self) -> Self:
        """Reject a directory string that is not a usable path shape.

        Existence is not checked: the writer creates the directory on the first run.

        Returns:
            The validated model.

        Raises:
            ValueError: If the value is blank, contains ``.`` or ``..``, has an empty
                segment, or names a CSV file instead of a directory.
        """
        segments = self._output_dir_segments()
        if not segments:
            raise ValueError("GITHUB_REPORT__OUTPUT_DIR_PATH must name a directory.")
        if any(segment == "" for segment in segments):
            raise ValueError("GITHUB_REPORT__OUTPUT_DIR_PATH must not contain empty segments.")
        if any(segment in {".", ".."} for segment in segments):
            raise ValueError("GITHUB_REPORT__OUTPUT_DIR_PATH must not contain '.' or '..'.")
        if segments[-1].lower().endswith(_CSV_SUFFIX):
            raise ValueError(
                "GITHUB_REPORT__OUTPUT_DIR_PATH is a directory, not a CSV file. "
                "The dated filename is added by the application."
            )
        return self

    @property
    def ORG_NAME(self) -> str:
        """The organization's login, as the GitHub API expects it.

        Returns:
            The single path segment of ``ORG_URL``, without slashes.
        """
        return self._path_segments()[0]

    @property
    def REPORT_PATH(self) -> Path:
        """Today's CSV path under ``OUTPUT_DIR_PATH``.

        The filename is ``YYYY_MM_DD_popular_github_repos.csv`` for the current UTC
        date. A second run on the same date therefore targets the same file.

        Returns:
            The directory from configuration plus the dated filename.
        """
        day = datetime.now(UTC).strftime("%Y_%m_%d")
        return Path(self.OUTPUT_DIR_PATH.strip()) / f"{day}{_REPORT_FILENAME_SUFFIX}"

    def _output_dir_segments(self) -> list[str]:
        """Split ``OUTPUT_DIR_PATH`` into segments.

        A trailing slash is ignored. An internal ``//`` still yields an empty segment
        so the validator can reject it. Leading slash and a Windows drive letter stay
        out of the segment list only when they are the root marker, not a name.

        Returns:
            The directory segments, in order. Empty when the value is blank.
        """
        normalized = self.OUTPUT_DIR_PATH.strip().replace("\\", "/")
        if not normalized:
            return []
        body = normalized.rstrip("/")
        parts = body.split("/")
        if normalized.startswith("/"):
            parts = parts[1:]
        return parts

    def _path_segments(self) -> list[str]:
        """Split the URL path into its non-empty segments.

        A trailing slash (``https://github.com/microsoft/``) is a common copy-paste
        artefact and yields the same single segment.

        Returns:
            The path segments, in order.
        """
        path = self.ORG_URL.path or ""
        return [segment for segment in path.split("/") if segment]
