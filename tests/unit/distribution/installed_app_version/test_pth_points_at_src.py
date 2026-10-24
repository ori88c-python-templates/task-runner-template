"""``pth_points_at_src`` against a fake dist and a temp ``.pth`` file."""

from pathlib import Path

from app.distribution.installed_app_version import pth_points_at_src
from tests.unit.distribution.installed_app_version.fake_pth_distribution import (
    FakePthDistribution,
    write_pth,
)


def test_pth_whose_contents_are_src_dir_returns_true(tmp_path: Path) -> None:
    """A ``.pth`` whose only line is ``src_dir`` identifies this checkout."""
    src_dir = tmp_path.resolve()
    pth = write_pth(tmp_path, f"{src_dir}\n")
    dist = FakePthDistribution(files=["editable.pth"], located={"editable.pth": pth})

    assert pth_points_at_src(dist, src_dir) is True


def test_comment_and_blank_lines_are_ignored(tmp_path: Path) -> None:
    """Comments and empty lines are skipped; a later matching path still counts."""
    src_dir = tmp_path.resolve()
    pth = write_pth(tmp_path, f"# editable install\n\n{src_dir}\n")
    dist = FakePthDistribution(files=["editable.pth"], located={"editable.pth": pth})

    assert pth_points_at_src(dist, src_dir) is True


def test_comment_only_pth_returns_false(tmp_path: Path) -> None:
    """A ``.pth`` that never names a directory is not this checkout."""
    src_dir = tmp_path.resolve()
    pth = write_pth(tmp_path, "# not a path\n\n")
    dist = FakePthDistribution(files=["editable.pth"], located={"editable.pth": pth})

    assert pth_points_at_src(dist, src_dir) is False


def test_pth_pointing_at_another_directory_returns_false(tmp_path: Path) -> None:
    """A ``.pth`` for a different src tree is not this checkout."""
    src_dir = (tmp_path / "src").resolve()
    src_dir.mkdir()
    other = (tmp_path / "other").resolve()
    other.mkdir()
    pth = write_pth(tmp_path, f"{other}\n")
    dist = FakePthDistribution(files=["editable.pth"], located={"editable.pth": pth})

    assert pth_points_at_src(dist, src_dir) is False


def test_missing_pth_file_returns_false(tmp_path: Path) -> None:
    """``locate_file`` pointing at a path that is not on disk is skipped."""
    src_dir = tmp_path.resolve()
    dist = FakePthDistribution(
        files=["gone.pth"],
        located={"gone.pth": tmp_path / "gone.pth"},
    )

    assert pth_points_at_src(dist, src_dir) is False


def test_non_pth_files_are_ignored(tmp_path: Path) -> None:
    """Only ``.pth`` members of ``files`` are read."""
    src_dir = tmp_path.resolve()
    other = tmp_path / "RECORD"
    other.write_text(f"{src_dir}\n", encoding="utf-8")
    dist = FakePthDistribution(files=["RECORD"], located={"RECORD": other})

    assert pth_points_at_src(dist, src_dir) is False


def test_none_files_returns_false(tmp_path: Path) -> None:
    """A dist that has not listed files is not this checkout."""
    dist = FakePthDistribution(files=None, located={})

    assert pth_points_at_src(dist, tmp_path.resolve()) is False
