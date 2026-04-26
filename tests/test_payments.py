"""Tests for :class:`PaymentsResource`."""

from __future__ import annotations

import httpx

from podpislon import PodpislonClient


async def test_list_systems(client: PodpislonClient, mock_api) -> None:
    mock_api.get("/pay-systems").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "result": [
                    {"id": 2, "name": "Robokassa"},
                    {"id": 5, "name": "ЮKassa"},
                ],
            },
        )
    )

    systems = await client.payments.list_systems()

    assert len(systems) == 2
    assert systems[0].id == 2
    assert systems[0].name == "Robokassa"
    assert systems[1].id == 5
    assert systems[1].name == "ЮKassa"


async def test_list_systems_empty(client: PodpislonClient, mock_api) -> None:
    mock_api.get("/pay-systems").mock(
        return_value=httpx.Response(200, json={"status": True, "result": []})
    )

    systems = await client.payments.list_systems()
    assert systems == []
