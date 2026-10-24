"""A dist-shaped test double for the editable ``.pth`` branch."""

from collections.abc import Sequence
from os import PathLike
from pathlib import Path


class FakePthDistribution:
    """A dist-shaped object: ``files``, ``locate_file``, and ``version``."""

    def __init__(
        self,
        *,
        files: Sequence[str] | None,
        located: dict[str, Path],
        version: str = "0.0.0",
    ) -> None:
        """Record the files a real distribution would expose.

        Args:
            files: Paths listed on the dist, or ``None`` when the dist has none.
            located: Map from those paths to filesystem locations.
            version: Unused by the helper; present so the object matches the protocol.
        """
        self.files = files
        self.version = version
        self._located = located

    def locate_file(self, path: str | PathLike[str]) -> Path:
        """Return the filesystem path recorded for ``path``.

        Args:
            path: A path from ``files``.

        Returns:
            The location supplied at construction.
        """
        return self._located[str(path)]


def write_pth(tmp_path: Path, contents: str, name: str = "editable.pth") -> Path:
    """Write ``contents`` to ``tmp_path / name`` and return that path.

    Args:
        tmp_path: Directory that owns the file.
        contents: Text of the ``.pth``.
        name: Filename, which must end in ``.pth``.

    Returns:
        The path of the written file.
    """
    pth = tmp_path / name
    pth.write_text(contents, encoding="utf-8")
    return pth
