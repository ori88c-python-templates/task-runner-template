"""Write the popular-repositories report to a dated CSV file."""

import csv
from collections.abc import Sequence
from io import StringIO
from pathlib import Path
from typing import Final

import aiofiles
import aiofiles.os
from structlog.typing import FilteringBoundLogger

from app.models import GithubRepoInfo

_COLUMNS: Final = ("rank", "name", "stars", "forks", "language")
_LINE_TERMINATOR: Final = "\n"


class CsvReportWriter:
    """Write the report to the CSV path from configuration.

    Opening the file for writing truncates it, so a second run that resolves to the
    same path replaces the file. The parent directory is created when it is missing.
    """

    def __init__(self, path: Path, logger: FilteringBoundLogger) -> None:
        """Store the destination file and the injected logger.

        Args:
            path: The CSV file, including the dated name. Production passes
                ``GithubReportConfig.REPORT_PATH``. Tests pass a temp path.
            logger: Child logger named after this class.
        """
        self._path: Final = path
        self._logger: Final = logger

    async def write(self, repos: Sequence[GithubRepoInfo]) -> None:
        """Create or replace the CSV with ``repos``.

        Args:
            repos: Repositories already ranked by stars, as produced by the adapter.
                An empty sequence still writes the header.
        """
        await aiofiles.os.makedirs(self._path.parent, exist_ok=True)
        async with aiofiles.open(self._path, "wb") as csv_file:
            await csv_file.write(_render(repos).encode("utf-8"))
        self._logger.info("csv_report.written", path=self._path.as_posix(), repos=len(repos))


def _render(repos: Sequence[GithubRepoInfo]) -> str:
    """Format the repositories as CSV text.

    Built in memory and then written as UTF-8 bytes, so the line endings are LF
    on Windows and Linux. A missing language is an empty field. Counts are plain
    integers.

    Args:
        repos: Ranked repositories. May be empty.

    Returns:
        The header and one row per repository, each ending in a newline.
    """
    buffer = StringIO(newline="")
    writer = csv.writer(buffer, lineterminator=_LINE_TERMINATOR)
    writer.writerow(_COLUMNS)
    writer.writerows(
        (
            index,
            repo.name,
            repo.stars,
            repo.forks,
            repo.language if repo.language is not None else "",
        )
        for index, repo in enumerate(repos, start=1)
    )
    return buffer.getvalue()
