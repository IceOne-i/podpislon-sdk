"""Tests for retry semantics across idempotent and non-idempotent methods.

Critical regression: ``client.documents.add`` (POST /add-document) creates
a new draft on every successful call. If a transient 5xx or read-side
error caused the SDK to retry, the user would end up with duplicate
documents on Podpislon's side. Methods that are *not* idempotent must only
be retried when we can prove the server never processed the original
request — i.e. on connect-side errors and on pre-handler statuses
(408 / 425 / 429).
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from podpislon import (
    PodpislonClient,
    PodpislonRateLimitError,
    PodpislonServerError,
    PodpislonTransportError,
)
from podpislon._transport import RetryPolicy


# ---------------------------------------------------------------------------
# RetryPolicy.should_retry_status
# ---------------------------------------------------------------------------
def test_policy_retries_5xx_on_get() -> None:
    policy = RetryPolicy(max_retries=3)
    assert policy.should_retry_status("GET", 500) is True
    assert policy.should_retry_status("GET", 503) is True


def test_policy_does_not_retry_5xx_on_post_by_default() -> None:
    policy = RetryPolicy(max_retries=3)
    assert policy.should_retry_status("POST", 500) is False
    assert policy.should_retry_status("PATCH", 502) is False


def test_policy_retries_429_even_on_post() -> None:
    policy = RetryPolicy(max_retries=3)
    assert policy.should_retry_status("POST", 429) is True
    assert policy.should_retry_status("PATCH", 429) is True


def test_policy_retries_put_and_delete() -> None:
    policy = RetryPolicy(max_retries=3)
    assert policy.should_retry_status("PUT", 500) is True
    assert policy.should_retry_status("DELETE", 503) is True


def test_policy_opt_in_to_post_retries() -> None:
    policy = RetryPolicy(max_retries=3, retry_non_idempotent=True)
    assert policy.should_retry_status("POST", 500) is True


# ---------------------------------------------------------------------------
# RetryPolicy.should_retry_exception
# ---------------------------------------------------------------------------
def test_policy_retries_connect_error_on_post() -> None:
    policy = RetryPolicy(max_retries=3)
    request = httpx.Request("POST", "https://example.com/")
    assert policy.should_retry_exception("POST", httpx.ConnectError("dns", request=request))
    assert policy.should_retry_exception(
        "POST", httpx.ConnectTimeout("timeout", request=request)
    )


def test_policy_does_not_retry_read_timeout_on_post() -> None:
    policy = RetryPolicy(max_retries=3)
    request = httpx.Request("POST", "https://example.com/")
    # ReadTimeout means the server may already be processing the request —
    # replaying could create a duplicate.
    assert policy.should_retry_exception(
        "POST", httpx.ReadTimeout("read timed out", request=request)
    ) is False
    assert policy.should_retry_exception(
        "POST", httpx.RemoteProtocolError("broken pipe", request=request)
    ) is False


def test_policy_retries_any_transport_exc_on_get() -> None:
    policy = RetryPolicy(max_retries=3)
    request = httpx.Request("GET", "https://example.com/")
    assert policy.should_retry_exception("GET", httpx.ReadTimeout("x", request=request))
    assert policy.should_retry_exception(
        "GET", httpx.RemoteProtocolError("x", request=request)
    )


# ---------------------------------------------------------------------------
# End-to-end: documents.add must not duplicate on transient failures.
# ---------------------------------------------------------------------------
async def test_add_document_does_not_retry_on_500() -> None:
    """The original bug: PUT /add-document was being retried on 5xx and
    creating duplicate drafts. Now it must surface the server error
    immediately."""

    async with PodpislonClient(
        api_key="test-key",
        rate_limit=None,
        max_retries=3,  # default; the policy must still refuse to retry
    ) as client:
        with respx.mock(base_url=client.base_url, assert_all_called=True) as router:
            route = router.put("/add-document").mock(
                return_value=httpx.Response(500, json={"error": "boom"})
            )

            with pytest.raises(PodpislonServerError):
                await client.documents.add(
                    name="Иван",
                    last_name="Иванов",
                    phone="+79991112233",
                    files=[b"%PDF-1.4 fake"],
                )

            # ← key assertion: exactly ONE attempt, no duplicates.
            assert route.call_count == 1


async def test_add_document_retries_on_429() -> None:
    """429 means the request was rejected before any side effect, so it's
    safe — and desirable — to retry POST."""

    async with PodpislonClient(
        api_key="test-key",
        rate_limit=None,
        max_retries=2,
    ) as client:
        with respx.mock(base_url=client.base_url) as router:
            route = router.put("/add-document").mock(
                side_effect=[
                    httpx.Response(429),
                    httpx.Response(200, json={"status": True, "result": 101}),
                ]
            )

            result = await client.documents.add(
                name="Иван",
                last_name="Иванов",
                phone="+79991112233",
                files=[b"%PDF-1.4"],
            )
            assert result.first_id == 101
            assert route.call_count == 2


async def test_get_info_still_retries_on_500() -> None:
    """GET is idempotent — 5xx must still be retried for it."""

    async with PodpislonClient(
        api_key="test-key",
        rate_limit=None,
        max_retries=2,
    ) as client:
        with respx.mock(base_url=client.base_url) as router:
            route = router.get("/get-info").mock(
                side_effect=[
                    httpx.Response(500),
                    httpx.Response(500),
                    httpx.Response(200, json={"status": True, "signings": "10", "company": {}}),
                ]
            )

            info = await client.company.get_info()
            assert info.signings == "10"
            assert route.call_count == 3


async def test_add_document_does_not_retry_on_read_timeout() -> None:
    """Read timeouts on POST might mean the server already processed the
    request. Replaying would risk a duplicate draft."""

    async with PodpislonClient(
        api_key="test-key",
        rate_limit=None,
        max_retries=3,
    ) as client:
        with respx.mock(base_url=client.base_url) as router:
            route = router.put("/add-document").mock(
                side_effect=httpx.ReadTimeout(
                    "read timed out",
                    request=httpx.Request("PUT", f"{client.base_url}/add-document"),
                )
            )

            with pytest.raises(PodpislonTransportError):
                await client.documents.add(
                    name="Иван",
                    last_name="Иванов",
                    phone="+79991112233",
                    files=[b"x"],
                )

            assert route.call_count == 1


async def test_add_document_retries_on_connect_error() -> None:
    """Connect errors happen before any bytes are sent — safe to replay."""

    async with PodpislonClient(
        api_key="test-key",
        rate_limit=None,
        max_retries=2,
    ) as client:
        with respx.mock(base_url=client.base_url) as router:
            route = router.put("/add-document").mock(
                side_effect=[
                    httpx.ConnectError(
                        "dns",
                        request=httpx.Request("PUT", f"{client.base_url}/add-document"),
                    ),
                    httpx.Response(200, json={"status": True, "result": 7}),
                ]
            )

            result = await client.documents.add(
                name="Иван",
                last_name="Иванов",
                phone="+79991112233",
                files=[b"x"],
            )
            assert result.first_id == 7
            assert route.call_count == 2


async def test_opt_in_retry_non_idempotent() -> None:
    """Callers with their own dedup can re-enable POST retries."""

    async with PodpislonClient(
        api_key="test-key",
        rate_limit=None,
        max_retries=2,
        retry_non_idempotent=True,
    ) as client:
        with respx.mock(base_url=client.base_url) as router:
            route = router.put("/add-document").mock(
                side_effect=[
                    httpx.Response(500),
                    httpx.Response(200, json={"status": True, "result": 42}),
                ]
            )

            result = await client.documents.add(
                name="Иван",
                last_name="Иванов",
                phone="+79991112233",
                files=[b"x"],
            )
            assert result.first_id == 42
            assert route.call_count == 2
