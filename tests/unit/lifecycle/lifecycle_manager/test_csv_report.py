"""The writer lands the CSV in the injected directory."""

from pathlib import Path

from app.lifecycle import LifecycleManager


async def test_run_writes_the_csv_into_the_injected_directory(
    lifecycle_manager: LifecycleManager,
    tmp_path: Path,
) -> None:
    """The mock search payload reaches the file, not stdout."""
    async with lifecycle_manager.create_task_runner() as task_runner:
        await task_runner.run()

    (path,) = tmp_path.glob("*_popular_github_repos.csv")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("rank,name,stars,forks,language\n")
    assert "vscode,1234,567,TypeScript" in text
    assert "docs,98,12," in text
