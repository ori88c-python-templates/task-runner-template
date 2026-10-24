"""The writer creates or replaces the CSV it was given."""

from io import BytesIO
from pathlib import Path

from app.logger import LogManager
from app.models import GithubRepoInfo
from app.services import CsvReportWriter
from tests.log_records import read_records

_FILENAME = "2026_10_24_popular_github_repos.csv"
_VSCODE = GithubRepoInfo(name="vscode", stars=1234, forks=567, language="TypeScript")
_DOCS = GithubRepoInfo(name="docs", stars=98, forks=12, language=None)


def _writer(log_manager: LogManager, path: Path) -> CsvReportWriter:
    """Build a writer aimed at ``path``.

    Args:
        log_manager: Shared test manager.
        path: Destination file, usually under a temp directory.

    Returns:
        The writer under test.
    """
    return CsvReportWriter(path, log_manager.get_child_logger("CsvReportWriter"))


async def test_writes_ranked_rows_and_an_empty_language(
    log_manager: LogManager,
    sink: BytesIO,
    tmp_path: Path,
) -> None:
    """Counts are plain integers, and a missing language is an empty field."""
    path = tmp_path / _FILENAME
    await _writer(log_manager, path).write([_VSCODE, _DOCS])

    assert path.read_text(encoding="utf-8") == (
        "rank,name,stars,forks,language\n1,vscode,1234,567,TypeScript\n2,docs,98,12,\n"
    )
    (record,) = [record for record in read_records(sink) if record["msg"] == "csv_report.written"]
    assert record["path"] == path.as_posix()
    assert record["repos"] == 2
    assert record["context"] == "CsvReportWriter"


async def test_empty_list_writes_the_header_only(log_manager: LogManager, tmp_path: Path) -> None:
    """An organization with no public repositories still produces the file."""
    path = tmp_path / _FILENAME
    await _writer(log_manager, path).write([])

    assert path.read_text(encoding="utf-8") == "rank,name,stars,forks,language\n"


async def test_a_second_write_replaces_the_file(log_manager: LogManager, tmp_path: Path) -> None:
    """Writing the same path truncates the previous report instead of appending."""
    path = tmp_path / _FILENAME
    writer = _writer(log_manager, path)
    await writer.write([_VSCODE, _DOCS])
    await writer.write([_DOCS])

    assert path.read_text(encoding="utf-8") == ("rank,name,stars,forks,language\n1,docs,98,12,\n")


async def test_a_missing_directory_is_created(log_manager: LogManager, tmp_path: Path) -> None:
    """The first run does not require the parent directory to exist already."""
    path = tmp_path / "github_reports" / _FILENAME
    await _writer(log_manager, path).write([_VSCODE])

    assert path.is_file()
