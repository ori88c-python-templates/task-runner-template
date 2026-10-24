"""``start`` probes ``/rate_limit`` and logs the remaining quota."""

from io import BytesIO

from tests.fake_github_search import MakeClient
from tests.log_records import read_records


async def test_start_probes_rate_limit_and_logs_remaining(
    make_client: MakeClient,
    sink: BytesIO,
) -> None:
    """The probe is the first request, and the leftover search and core quota are logged."""
    client, mocked = make_client()

    await client.start()

    try:
        (request,) = mocked.requests
        assert request.url.path.endswith("/rate_limit")
        (record,) = [record for record in read_records(sink) if record["msg"] == "github.started"]
        assert record["search_remaining"] == 9
        assert record["core_remaining"] == 59
        assert record["context"] == "GithubClient"
    finally:
        await client.stop()
