"""Shared pytest fixtures."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest
import pytest_asyncio
import respx

from podpislon import PodpislonClient
from podpislon.client import DEFAULT_BASE_URL


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    """Module-scoped loop avoids per-test loop teardown noise on Windows."""

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def base_url() -> str:
    return DEFAULT_BASE_URL


@pytest_asyncio.fixture
async def client() -> AsyncIterator[PodpislonClient]:
    """A fresh client with rate limiting disabled (faster tests)."""

    instance = PodpislonClient(
        api_key="test-key",
        rate_limit=None,
        max_retries=0,
    )
    try:
        yield instance
    finally:
        await instance.aclose()


@pytest.fixture
def mock_api(base_url: str):
    """Spin up respx with the same base URL the client uses."""

    with respx.mock(base_url=base_url, assert_all_called=False) as router:
        yield router
