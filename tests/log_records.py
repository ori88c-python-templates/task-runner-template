"""Read back what a :class:`LogManager` wrote to an injected buffer.

Kept separate from ``conftest.py`` because fixtures are discovered by pytest while these are
imported by name, and importing from a conftest module is discouraged.
"""

import io
import json
from typing import Any


def read_records(stream: io.BytesIO) -> list[dict[str, Any]]:
    """Parse everything written to ``stream`` as newline-delimited JSON.

    Args:
        stream: The buffer a manager has been writing to.

    Returns:
        One dict per emitted record, in the order they were written.

    Raises:
        UnicodeDecodeError: If the output is not valid UTF-8, which is itself a failure
            worth surfacing rather than hiding behind a replacement character.
    """
    text = stream.getvalue().decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def read_messages(stream: io.BytesIO) -> list[str]:
    """Return the ``msg`` of every record written to ``stream``, in order.

    Args:
        stream: The buffer a manager has been writing to.

    Returns:
        One event name per emitted record.
    """
    return [record["msg"] for record in read_records(stream)]
