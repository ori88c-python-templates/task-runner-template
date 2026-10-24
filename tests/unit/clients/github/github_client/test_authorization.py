"""The ``Authorization`` header is present only when a token was configured."""

from tests.fake_github_search import MakeClient


async def test_unauthenticated_requests_have_no_authorization_header(
    make_client: MakeClient,
) -> None:
    """The demo run without a token must not send a forged or empty header."""
    client, mocked = make_client()
    await client.start()
    try:
        await client.search_repositories_by_stars("acme", 2)
    finally:
        await client.stop()

    assert all("authorization" not in request.headers for request in mocked.requests)


async def test_token_is_sent_as_the_authorization_header(make_client: MakeClient) -> None:
    """The SDK's token strategy prefixes the value with ``token``."""
    client, mocked = make_client(token="ghs_test")
    await client.start()
    try:
        await client.search_repositories_by_stars("acme", 2)
    finally:
        await client.stop()

    assert all(request.headers["authorization"] == "token ghs_test" for request in mocked.requests)
