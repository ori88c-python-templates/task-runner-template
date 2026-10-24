"""A dotenv file maps onto the nested models, and nothing unknown slips through."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import LogLevel
from tests.load_app_config import load_app_config


def test_nested_keys_reach_their_resource_model(tmp_path: Path) -> None:
    """``LOGGER__MIN_LOG_LEVEL`` lands on ``AppConfig.logger.MIN_LOG_LEVEL``."""
    env_file = tmp_path / ".env"
    env_file.write_text("LOGGER__MIN_LOG_LEVEL=error\n", encoding="utf-8")

    config = load_app_config(env_file)

    assert config.logger.MIN_LOG_LEVEL is LogLevel.ERROR


def test_unknown_key_fails_at_startup(tmp_path: Path) -> None:
    """A stale or misspelled variable is an error, not a silently ignored setting."""
    env_file = tmp_path / ".env"
    env_file.write_text("REDIS__HOST=127.0.0.1\n", encoding="utf-8")

    with pytest.raises(ValidationError) as exc_info:
        load_app_config(env_file)

    (error,) = exc_info.value.errors()
    assert error["type"] == "extra_forbidden"
    assert error["loc"] == ("redis__host",)
