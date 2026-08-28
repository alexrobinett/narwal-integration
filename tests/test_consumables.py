"""consumable/get_consumable_info decode and the client fetch seam.

Response after-frame (sniffed from the app 2026-08-27): {1: ConsumableInfo
{1: maintainItems packed varints, 2: replaceItems packed varints}} with NO
result varint — the robot answered a bare `0a00` (nothing needs attention).
Because the app payload keeps the echoed auth fields in front of that tail,
CommandResponse sees result 0 / no data; the client must read `raw`, where
the last-wins parser resolves field 1 to the trailing consumable payload.
"""

import asyncio

from narwal_client.client import NarwalClient, NarwalCommandError, _make_protobuf_string
from narwal_client.const import (
    CONSUMABLE_MAINTAIN_NAMES,
    CONSUMABLE_REPLACE_NAMES,
    MOP_HUMIDITY_NAMES_ZULTRA,
)
from narwal_client.models import CommandResponse, NarwalState

ZULTRA_KEY = "hEA7OEshlx"
UUID = "0" * 32


def _len_field(field: int, payload: bytes) -> bytes:
    assert len(payload) < 128
    return bytes([(field << 3) | 2, len(payload)]) + payload


def _consumables(maintain: list[int], replace: list[int]) -> bytes:
    """{1: {1: packed maintain ids, 2: packed replace ids}} — empty lists omit the sub-field."""
    inner = b""
    if maintain:
        inner += _len_field(1, bytes(maintain))
    if replace:
        inner += _len_field(2, bytes(replace))
    return _len_field(1, inner)


def test_maintain_and_replace_lists_are_decoded():
    s = NarwalState(profile="zultra")
    s.update_consumable_info(_consumables([4, 6, 8, 10], [3, 20]))
    assert s.consumables_maintain == [4, 6, 8, 10]
    assert s.consumables_replace == [3, 20]


def test_helper_builds_the_expected_wire_bytes():
    assert _consumables([4, 6, 8, 10], [3, 20]) == bytes.fromhex("0a0a" "0a04" "0406080a" "1202" "0314")


def test_empty_payload_means_nothing_needs_attention():
    for payload in (b"", b"\x0a\x00"):
        s = NarwalState(profile="zultra")
        s.consumables_maintain = [1]
        s.consumables_replace = [2]
        s.update_consumable_info(payload)
        assert s.consumables_maintain == []
        assert s.consumables_replace == []


def test_only_replace_items():
    s = NarwalState(profile="zultra")
    s.update_consumable_info(_consumables([], [8]))
    assert s.consumables_maintain == []
    assert s.consumables_replace == [8]


def test_printable_packed_values_survive_the_str_parser_path():
    # values >= 0x20 decode as printable text in parse_protobuf_fields; they
    # must be re-encoded byte-for-byte, not dropped
    s = NarwalState(profile="zultra")
    s.update_consumable_info(_consumables([33, 34], [65]))
    assert s.consumables_maintain == [33, 34]
    assert s.consumables_replace == [65]


def test_non_ascii_printable_text_is_reencoded_byte_exact():
    # c3 a9 41 ("éA") is printable UTF-8, so the parser hands back a str; a
    # latin-1 re-encode would turn it into e9 41 and decode a different id
    s = NarwalState(profile="zultra")
    s.update_consumable_info(_len_field(1, _len_field(1, bytes([0xC3, 0xA9, 0x41]))))
    assert s.consumables_maintain == [0x43 | (0x29 << 7) | (0x41 << 14)]


def test_multibyte_varints_are_decoded():
    # 300 = 0xac 0x02 as a varint, packed after a 1
    s = NarwalState(profile="zultra")
    s.update_consumable_info(_len_field(1, _len_field(1, bytes([1, 0xAC, 0x02]))))
    assert s.consumables_maintain == [1, 300]


def test_state_defaults_are_empty():
    s = NarwalState()
    assert s.consumables_maintain == []
    assert s.consumables_replace == []


def _client() -> NarwalClient:
    return NarwalClient(
        product_key=ZULTRA_KEY, device_name="d", user_uuid=UUID,
        mqtt_username=UUID, mqtt_password="p",
    )


def _app_payload(tail: bytes) -> bytes:
    """What _extract_app_payload hands to CommandResponse: echoed auth fields + tail."""
    return _make_protobuf_string(1, UUID) + _make_protobuf_string(2, UUID) + tail


def test_fetch_consumables_reads_the_response_tail():
    client = _client()
    calls: list = []

    async def fake_send(command, extra_payload=b"", timeout=None, payload_override=None):
        calls.append(command)
        return CommandResponse.from_payload(_app_payload(_consumables([1], [2, 8])))

    client.send_command = fake_send
    assert asyncio.run(client.fetch_consumables()) is True

    assert calls == ["consumable/get_consumable_info"]
    assert client.state.consumables_maintain == [1]
    assert client.state.consumables_replace == [2, 8]


def test_fetch_consumables_sniffed_empty_response():
    client = _client()
    client.state.consumables_replace = [8]

    async def fake_send(command, extra_payload=b"", timeout=None, payload_override=None):
        resp = CommandResponse.from_payload(_app_payload(b"\x0a\x00"))
        assert resp.success is False and resp.data == b""  # documents why raw is used
        return resp

    client.send_command = fake_send
    asyncio.run(client.fetch_consumables())

    assert client.state.consumables_maintain == []
    assert client.state.consumables_replace == []


def test_fetch_consumables_timeout_leaves_state_unchanged():
    client = _client()
    client.state.consumables_maintain = [4]

    async def fake_send(command, extra_payload=b"", timeout=None, payload_override=None):
        raise NarwalCommandError("timed out")

    client.send_command = fake_send
    assert asyncio.run(client.fetch_consumables()) is False

    assert client.state.consumables_maintain == [4]


def test_name_tables():
    assert CONSUMABLE_MAINTAIN_NAMES[1] == "Dust box"
    assert CONSUMABLE_MAINTAIN_NAMES[20] == "Dust container"
    assert CONSUMABLE_REPLACE_NAMES[8] == "Dust bag"
    assert CONSUMABLE_REPLACE_NAMES[24] == "Inner dust box"
    assert len(CONSUMABLE_MAINTAIN_NAMES) == 10
    assert len(CONSUMABLE_REPLACE_NAMES) == 13
    assert MOP_HUMIDITY_NAMES_ZULTRA == {1: "Dry", 2: "Normal", 3: "Wet"}
