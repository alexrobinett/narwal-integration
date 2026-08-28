"""Client seam for dock actions: Z Ultra supply/* commands are fire-and-forget."""

import asyncio

from narwal_client.client import NarwalClient
from narwal_client.models import CommandResponse

ZULTRA_KEY = "hEA7OEshlx"
LEGACY_KEY = "EHf6cRNRGT"


def _client(product_key: str) -> NarwalClient:
    return NarwalClient(
        product_key=product_key,
        device_name="d",
        user_uuid="u",
        mqtt_username="u",
        mqtt_password="p",
    )


def _instrument(client: NarwalClient) -> tuple[list, list]:
    """Replace both send paths with async recorders; return (no_response_calls, response_calls)."""
    no_response_calls: list = []
    response_calls: list = []

    async def fake_no_response(command, extra_payload=b"", payload_override=None):
        no_response_calls.append((command, extra_payload, payload_override))

    async def fake_send(command, extra_payload=b"", timeout=None, payload_override=None):
        response_calls.append((command, extra_payload, payload_override))
        return CommandResponse(result_code=1, success=True)

    client.send_command_no_response = fake_no_response
    client.send_command = fake_send
    return no_response_calls, response_calls


def test_zultra_recall_is_fire_and_forget():
    client = _client(ZULTRA_KEY)
    no_response_calls, response_calls = _instrument(client)

    resp = asyncio.run(client.return_to_base())

    assert no_response_calls == [("supply/recall", b"", None)]
    assert response_calls == []
    assert isinstance(resp, CommandResponse)
    assert resp.success is True


def test_legacy_recall_awaits_response():
    client = _client(LEGACY_KEY)
    no_response_calls, response_calls = _instrument(client)

    resp = asyncio.run(client.return_to_base())

    assert response_calls == [("supply/recall", b"", None)]
    assert no_response_calls == []
    assert resp.success is True


def test_dock_actions_send_standard_frame_without_response():
    client = _client(ZULTRA_KEY)
    no_response_calls, response_calls = _instrument(client)

    for method in ("wash_mop", "dry_mop", "empty_dustbin"):
        resp = asyncio.run(getattr(client, method)())
        assert isinstance(resp, CommandResponse)
        assert resp.success is True

    assert no_response_calls == [
        ("supply/wash_and_dry_mop", b"", None),
        ("supply/dry_mop", b"", None),
        ("supply/dust_gathering", b"", None),
    ]
    assert response_calls == []


def test_zultra_wash_mop_uses_wash_and_dry_topic():
    """Sniffed from the official app: 'Mop washing' publishes supply/wash_and_dry_mop;
    supply/wash_mop returns NOT_APPLICABLE (result 2) on the Freo Z Ultra."""
    client = _client(ZULTRA_KEY)
    no_response_calls, response_calls = _instrument(client)

    resp = asyncio.run(client.wash_mop())

    assert no_response_calls == [("supply/wash_and_dry_mop", b"", None)]
    assert response_calls == []
    assert resp.success is True


def test_legacy_wash_mop_keeps_upstream_topic():
    client = _client(LEGACY_KEY)
    no_response_calls, response_calls = _instrument(client)

    resp = asyncio.run(client.wash_mop())

    assert no_response_calls == [("supply/wash_mop", b"", None)]
    assert response_calls == []
    assert resp.success is True
