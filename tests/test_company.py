"""Tests for :class:`CompanyResource`."""

from __future__ import annotations

import httpx

from podpislon import PodpislonClient


async def test_get_info_returns_company(client: PodpislonClient, mock_api) -> None:
    mock_api.get("/get-info").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "signings": "259",
                "company": {
                    "name": 'ООО "Рога и копыта"',
                    "inn": "1001982736",
                    "kpp": "123456789",
                },
            },
        )
    )

    info = await client.company.get_info()

    assert info.signings == "259"
    assert info.signings_left == 259
    assert info.company.name == 'ООО "Рога и копыта"'
    assert info.company.inn == "1001982736"
    assert info.company.kpp == "123456789"


async def test_get_info_handles_missing_signings(
    client: PodpislonClient, mock_api
) -> None:
    mock_api.get("/get-info").mock(
        return_value=httpx.Response(200, json={"status": True, "company": {}})
    )

    info = await client.company.get_info()
    assert info.signings is None
    assert info.signings_left is None
    assert info.company.name is None


async def test_get_info_signings_left_tolerates_garbage(
    client: PodpislonClient, mock_api
) -> None:
    mock_api.get("/get-info").mock(
        return_value=httpx.Response(
            200, json={"status": True, "signings": "n/a", "company": {}}
        )
    )

    info = await client.company.get_info()
    assert info.signings == "n/a"
    assert info.signings_left is None


async def test_get_info_accepts_integer_signings(
    client: PodpislonClient, mock_api
) -> None:
    """Regression: the live API returns ``signings`` as an int, not a string."""

    mock_api.get("/get-info").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "signings": 10,
                "company": {"name": "Acme", "inn": 1234567890, "kpp": 987654321},
            },
        )
    )

    info = await client.company.get_info()
    assert info.signings == "10"
    assert info.signings_left == 10
    assert info.company.inn == "1234567890"
    assert info.company.kpp == "987654321"
