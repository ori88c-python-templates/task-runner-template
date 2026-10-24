"""``installed_app_version`` smoke and injected catalogs (no importlib patching)."""

from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

from app.distribution import installed_app_version
from tests.unit.distribution.installed_app_version.fake_pth_distribution import (
    FakePthDistribution,
    write_pth,
)


def test_this_checkout_reports_a_non_empty_version() -> None:
    """The editable ``.pth`` install in this environment yields a version string."""
    result = installed_app_version()

    assert isinstance(result, str)
    assert result


def test_wheel_mapping_uses_the_injected_version_lookup() -> None:
    """A ``packages_distributions`` hit does not scan ``.pth`` files."""
    result = installed_app_version(
        mapped_names={"app": ["task-runner-template"]},
        version_for=lambda name: f"{name}-9.9.9",
        dists=(),
    )

    assert result == "task-runner-template-9.9.9"


def test_editable_pth_uses_the_matching_dist_version(tmp_path: Path) -> None:
    """With an empty import map, a ``.pth`` that names ``src_dir`` wins."""
    src_dir = tmp_path.resolve()
    pth = write_pth(tmp_path, f"{src_dir}\n")
    dist = FakePthDistribution(
        files=["editable.pth"],
        located={"editable.pth": pth},
        version="1.2.3",
    )

    result = installed_app_version(mapped_names={}, dists=[dist], src_dir=src_dir)

    assert result == "1.2.3"


def test_empty_catalogs_raise_package_not_found() -> None:
    """No wheel mapping and no matching ``.pth`` is the same as a missing dist."""
    with pytest.raises(PackageNotFoundError):
        installed_app_version(mapped_names={}, dists=())
