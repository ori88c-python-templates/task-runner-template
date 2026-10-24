"""UTF-8 output, asserted against the raw bytes of a real file on disk.

These go through an actual file rather than an in-memory buffer because the bug that
prompted this suite lived in the stream layer, which an in-memory sink would not have
exercised.
"""

import io
import json
from pathlib import Path

import pytest

from app.config import Environment, LoggerConfig, LogLevel
from app.logger.log_manager import LogManager
from tests.log_records import read_records
from tests.unit.logger.log_manager.helpers import ManagerFactory

HEBREW = "בר מצווה"
EMOJI = "✓ 🚀"
CJK = "日本語テキスト"


def _log_to_file(path: Path, **fields: object) -> bytes:
    """Write one record to ``path`` and return the raw bytes it produced.

    Args:
        path: File to write to. Opened in binary mode, as the manager expects.
        **fields: Keyword arguments passed straight through to the log call.

    Returns:
        The exact bytes on disk after the manager has flushed and the file is closed.
    """
    with path.open("wb") as handle:
        manager = LogManager(
            LoggerConfig(MIN_LOG_LEVEL=LogLevel.DEBUG),
            env=Environment.DEV,
            app_version="0.1.0",
            stream=handle,
        )
        manager.get_child_logger("UsersService").info("user.created", **fields)
        manager.flush()

    return path.read_bytes()


def test_non_ascii_values_are_written_as_literal_utf8(tmp_path: Path) -> None:
    r"""No ``\uXXXX`` escaping: the bytes on disk are the characters themselves."""
    raw = _log_to_file(tmp_path / "app.log", name=HEBREW, mark=EMOJI, text=CJK)

    assert rb"\u" not in raw
    assert HEBREW.encode("utf-8") in raw
    assert EMOJI.encode("utf-8") in raw
    assert CJK.encode("utf-8") in raw


def test_bytes_on_disk_decode_and_round_trip_exactly(tmp_path: Path) -> None:
    """Reading the file back yields the original strings, not mangled ones."""
    raw = _log_to_file(tmp_path / "app.log", name=HEBREW, mark=EMOJI, text=CJK)

    record = json.loads(raw.decode("utf-8"))
    assert record["name"] == HEBREW
    assert record["mark"] == EMOJI
    assert record["text"] == CJK


def test_no_byte_order_mark_or_replacement_characters(tmp_path: Path) -> None:
    """A BOM or a lossy substitution would break downstream JSON parsers."""
    raw = _log_to_file(tmp_path / "app.log", name=HEBREW)

    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"?" not in raw
    assert "\ufffd" not in raw.decode("utf-8")


def test_file_ends_with_a_newline_per_record(tmp_path: Path) -> None:
    """Newline-delimited JSON needs the delimiter, including on the last line."""
    raw = _log_to_file(tmp_path / "app.log", name=HEBREW)

    assert raw.endswith(b"\n")
    assert raw.count(b"\n") == 1


def test_non_ascii_field_names_survive(make_manager: ManagerFactory, sink: io.BytesIO) -> None:
    """Keys are encoded the same way values are."""
    make_manager().get_child_logger("UsersService").info("user.created", **{"שם": HEBREW})

    (record,) = read_records(sink)
    assert record["שם"] == HEBREW


def test_non_ascii_message_survives(make_manager: ManagerFactory, sink: io.BytesIO) -> None:
    """The renamed ``msg`` key is not a special case."""
    make_manager().get_child_logger("UsersService").info(CJK)

    (record,) = read_records(sink)
    assert record["msg"] == CJK


def test_bytes_values_are_decoded_to_text(make_manager: ManagerFactory, sink: io.BytesIO) -> None:
    """``UnicodeDecoder`` turns byte payloads into strings the serializer can handle."""
    make_manager().get_child_logger("UsersService").info(
        "user.created", name=HEBREW.encode("utf-8")
    )

    (record,) = read_records(sink)
    assert record["name"] == HEBREW


@pytest.mark.parametrize("value", ['quote"inside', "back\\slash", "new\nline", "tab\there"])
def test_characters_that_need_json_escaping_round_trip(
    make_manager: ManagerFactory, sink: io.BytesIO, value: str
) -> None:
    """Disabling ASCII escaping must not disable JSON's own structural escaping."""
    make_manager().get_child_logger("UsersService").info("user.created", value=value)

    (record,) = read_records(sink)
    assert record["value"] == value
