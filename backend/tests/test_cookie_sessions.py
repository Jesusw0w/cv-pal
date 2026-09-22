from httpx import AsyncClient

from cv_pal.constants import (
    DEFAULT_ACCESS_COOKIE,
    DEFAULT_REFRESH_COOKIE,
    DEFAULT_SESSION_HEADER,
)
from tests.helpers import DEFAULT_TEST_EMAIL, DEFAULT_TEST_PASSWORD

COOKIE_MODE = {DEFAULT_SESSION_HEADER: "cookie"}


async def cookie_login(client: AsyncClient) -> None:
    """Register and sign in as a browser does, leaving the cookies in the client jar.

    Args:
        client: The test HTTP client.
    """
    await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )
    response = await client.post(
        "/auth/login",
        headers=COOKIE_MODE,
        data={"username": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )
    assert response.status_code == 200


async def test_cookie_login_keeps_tokens_out_of_the_body(client: AsyncClient) -> None:
    """Page script must never see a token, so the body carries neither."""
    await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )
    response = await client.post(
        "/auth/login",
        headers=COOKIE_MODE,
        data={"username": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )

    body = response.json()
    assert body["access_token"] is None
    assert body["refresh_token"] is None
    set_cookies = response.headers.get_list("set-cookie")
    assert len(set_cookies) == 2
    for header in set_cookies:
        assert "HttpOnly" in header
        assert "SameSite=strict" in header


async def test_cookie_session_authenticates_with_the_header(
    client: AsyncClient,
) -> None:
    """The cookie plus the session header is a signed-in request."""
    await cookie_login(client)

    response = await client.get("/users/me", headers=COOKIE_MODE)

    assert response.status_code == 200
    assert response.json()["email"] == DEFAULT_TEST_EMAIL


async def test_cookie_without_the_header_is_refused(client: AsyncClient) -> None:
    """A cross-site form can send the cookie but not the header — so it gets nothing."""
    await cookie_login(client)

    assert (await client.get("/users/me")).status_code == 401


async def test_cookie_refresh_rotates_both_cookies(client: AsyncClient) -> None:
    """Refresh reads the cookie and answers with new cookies, not a body."""
    await cookie_login(client)
    old_refresh = client.cookies[DEFAULT_REFRESH_COOKIE]

    response = await client.post("/auth/refresh", headers=COOKIE_MODE)

    assert response.status_code == 200
    assert response.json()["refresh_token"] is None
    assert client.cookies[DEFAULT_REFRESH_COOKIE] != old_refresh
    assert (await client.get("/users/me", headers=COOKIE_MODE)).status_code == 200


async def test_cookie_logout_revokes_and_clears(client: AsyncClient) -> None:
    """Logging out ends the session server-side and drops both cookies."""
    await cookie_login(client)
    refresh = client.cookies[DEFAULT_REFRESH_COOKIE]

    response = await client.post("/auth/logout", headers=COOKIE_MODE)

    assert response.status_code == 204
    assert DEFAULT_ACCESS_COOKIE not in client.cookies
    assert DEFAULT_REFRESH_COOKIE not in client.cookies
    replay = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert replay.status_code == 401


async def test_refresh_with_nothing_presented_is_refused(client: AsyncClient) -> None:
    """No body and no cookie is an invalid refresh, not a server error."""
    assert (await client.post("/auth/refresh")).status_code == 401
