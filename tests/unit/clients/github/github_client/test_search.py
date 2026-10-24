"""Search asks GitHub for the org's repositories, sorted by stars descending."""

from io import BytesIO

from tests.fake_github_search import MakeClient
from tests.log_records import read_records


async def test_search_request_is_sorted_by_stars_descending(
    make_client: MakeClient,
    sink: BytesIO,
) -> None:
    """One Search API call carries ``q``, ``sort``, ``order``, and ``per_page``."""
    client, mocked = make_client()
    await client.start()

    try:
        items = await client.search_repositories_by_stars("acme", 3)
    finally:
        await client.stop()

    search_requests = [request for request in mocked.requests if "search" in request.url.path]
    (request,) = search_requests
    assert request.url.params["q"] == "org:acme"
    assert request.url.params["sort"] == "stars"
    assert request.url.params["order"] == "desc"
    assert request.url.params["per_page"] == "3"
    assert [item.name for item in items] == ["vscode", "docs"]
    (record,) = [
        record for record in read_records(sink) if record["msg"] == "github.search.completed"
    ]
    assert record["total_count"] == 2
    assert record["returned"] == 2


async def test_incomplete_results_are_logged(
    make_client: MakeClient,
    sink: BytesIO,
) -> None:
    """A truncated search is a warning, and the items that did arrive are still returned."""
    client, _mocked = make_client(incomplete_results=True)
    await client.start()

    try:
        items = await client.search_repositories_by_stars("acme", 2)
    finally:
        await client.stop()

    assert [item.name for item in items] == ["vscode", "docs"]
    (record,) = [
        record for record in read_records(sink) if record["msg"] == "github.search.incomplete"
    ]
    assert record["org"] == "acme"
    assert record["level"] == "warning"
