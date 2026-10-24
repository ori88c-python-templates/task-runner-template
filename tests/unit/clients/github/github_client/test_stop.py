"""``stop`` is safe when ``start`` never ran."""

from tests.fake_github_search import MakeClient


async def test_stop_without_start_is_safe(make_client: MakeClient) -> None:
    """An empty exit stack closes nothing, so a failed startup can still tear down."""
    client, mocked = make_client()

    await client.stop()

    assert mocked.requests == []
