"""The optional token stays a ``SecretStr`` and never appears in the repr."""

from pydantic import SecretStr

from app.config import GithubReportConfig


def test_token_is_a_secret_str() -> None:
    """A configured token is wrapped so dumps and reprs cannot leak it."""
    config = GithubReportConfig.model_validate({"TOKEN": "ghs_test"})

    assert isinstance(config.TOKEN, SecretStr)
    assert config.TOKEN.get_secret_value() == "ghs_test"
    assert "ghs_test" not in repr(config)
