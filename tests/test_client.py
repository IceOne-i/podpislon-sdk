"""Tests for the top-level :class:`PodpislonClient`."""

from __future__ import annotations

import httpx
import pytest

from podpislon import (
    PodpislonAuthenticationError,
    PodpislonClient,
    PodpislonConfigurationError,
    PodpislonRateLimitError,
    PodpislonServerError,
)


def test_requires_api_key() -> None:
    with pytest.raises(PodpislonConfigurationError):
        PodpislonClient(api_key="")


def test_requires_string_api_key() -> None:
    with pytest.raises(PodpislonConfigurationError):
        PodpislonClient(api_key=None)  # type: ignore[arg-type]


def test_requires_base_url() -> None:
    with pytest.raises(PodpislonConfigurationError):
        PodpislonClient(api_key="x", base_url="")


def test_repr_contains_base_url() -> None:
    client = PodpislonClient(api_key="x")
    assert "podpislon.ru" in repr(client)


async def test_close_is_idempotent() -> None:
    client = PodpislonClient(api_key="x")
    await client.aclose()
    await client.aclose()  # second call must not raise


async def test_attaches_api_key_header(client: PodpislonClient, mock_api) -> None:
    route = mock_api.get("/get-info").mock(
        return_value=httpx.Response(200, json={"status": True, "signings": "10", "company": {}}),
    )
    await client.company.get_info()
    assert route.called
    assert route.calls.last.request.headers.get("X-Api-Key") == "test-key"


async def test_401_raises_authentication_error(client: PodpislonClient, mock_api) -> None:
    mock_api.get("/get-info").mock(return_value=httpx.Response(401, json={"error": "bad key"}))
    with pytest.raises(PodpislonAuthenticationError):
        await client.company.get_info()


async def test_429_raises_after_retries_exhausted(client: PodpislonClient, mock_api) -> None:
    mock_api.get("/get-info").mock(return_value=httpx.Response(429, json={"error": "slow down"}))
    with pytest.raises(PodpislonRateLimitError):
        await client.company.get_info()


async def test_500_raises_server_error(client: PodpislonClient, mock_api) -> None:
    mock_api.get("/get-info").mock(return_value=httpx.Response(500, json={"error": "boom"}))
    with pytest.raises(PodpislonServerError):
        await client.company.get_info()


async def test_request_escape_hatch_returns_raw_json(
    client: PodpislonClient, mock_api
) -> None:
    mock_api.get("/get-info").mock(return_value=httpx.Response(200, json={"hello": "world"}))
    body = await client.request("GET", "/get-info")
    assert body == {"hello": "world"}
