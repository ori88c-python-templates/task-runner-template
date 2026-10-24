"""Build ``AppConfig`` the way production does, minus the working directory's ``.env``."""

from pathlib import Path

from app.config import AppConfig


def load_app_config(env_file: Path | None = None) -> AppConfig:
    """Load configuration from the process environment and ``env_file`` only.

    A developer's own ``.env`` must neither change what a test sees nor fail it. The
    process environment still applies, exactly as in production.

    Args:
        env_file: Dotenv file to read, or ``None`` to read none at all.

    Returns:
        The validated configuration.
    """
    # pydantic-settings accepts `_env_file` at runtime, but the dataclass transform pyright
    # sees only declares the model's fields.
    return AppConfig(_env_file=env_file)  # pyright: ignore[reportCallIssue]
