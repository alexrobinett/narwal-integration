"""Both publish paths must use QoS 0.

Narwal's broker never PUBACKs app publishes; at QoS 1 paho stops transmitting
after 20 un-acked messages (max_inflight), so every later command silently
stalls. These tests pin the real ``publish(...)`` arguments on both sites.
"""

import asyncio

import pytest

import narwal_client.client as client_module
from narwal_client.client import NarwalClient, NarwalCommandError

ZULTRA_KEY = "hEA7OEshlx"


class _PublishResult:
    rc = 0
    mid = 1

    def is_published(self) -> bool:
        return True


class FakePaho:
    """Records publish/subscribe calls; never delivers a response."""

    def __init__(self) -> None:
        self.publishes: list[dict] = []
        self.subscribes: list[tuple[str, int]] = []

    def publish(self, topic, payload, qos, properties):
        self.publishes.append(
            {"topic": topic, "payload": payload, "qos": qos, "properties": properties}
        )
        return _PublishResult()

    def subscribe(self, topic, qos):
        self.subscribes.append((topic, qos))
        return (0, 1)


def _connected_client() -> tuple[NarwalClient, FakePaho]:
    client = NarwalClient(
        product_key=ZULTRA_KEY,
        device_name="d",
        user_uuid="u",
        mqtt_username="u",
        mqtt_password="p",
    )
    fake = FakePaho()
    client._client = fake
    client._connected.set()
    return client, fake


def test_no_response_publish_uses_qos0():
    client, fake = _connected_client()

    asyncio.run(client.send_command_no_response("supply/dust_gathering"))

    assert len(fake.publishes) == 1
    publish = fake.publishes[0]
    assert publish["topic"].endswith("/supply/dust_gathering")
    assert publish["qos"] == 0


def test_command_publish_uses_qos0(monkeypatch):
    client, fake = _connected_client()
    monkeypatch.setattr(client_module.time, "sleep", lambda _s: None)

    with pytest.raises(NarwalCommandError):
        client._send_command_locked("status/get_device_base_status", b"", 0.01)

    assert len(fake.publishes) == 1
    publish = fake.publishes[0]
    assert publish["topic"].endswith("/status/get_device_base_status")
    assert publish["qos"] == 0
