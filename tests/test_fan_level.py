from narwal_client.client import NarwalClient
from narwal_client.const import FanLevel, fan_level_from_wire, fan_wire_value


def test_zultra_sends_one_based_fan_levels():
    assert fan_wire_value("hEA7OEshlx", FanLevel.QUIET) == 1
    assert fan_wire_value("hEA7OEshlx", FanLevel.MAX) == 4


def test_x_ultra_keeps_zero_based_fan_levels():
    assert fan_wire_value("EHf6cRNRGT", FanLevel.QUIET) == 0
    assert fan_wire_value("EHf6cRNRGT", FanLevel.MAX) == 3


def test_fan_level_from_wire_round_trips():
    assert fan_level_from_wire("hEA7OEshlx", 4) == FanLevel.MAX
    assert fan_level_from_wire("hEA7OEshlx", 1) == FanLevel.QUIET
    assert fan_level_from_wire("EHf6cRNRGT", 0) == FanLevel.QUIET
    assert fan_level_from_wire("hEA7OEshlx", 9) is None
    assert fan_level_from_wire("EHf6cRNRGT", 9) is None


def _client(product_key: str) -> NarwalClient:
    return NarwalClient(
        product_key=product_key,
        device_name="d",
        user_uuid="u",
        mqtt_username="u",
        mqtt_password="p",
    )


def test_client_fan_level_is_none_when_unreported():
    assert _client("hEA7OEshlx").fan_level is None


def test_client_fan_level_zultra_decodes_wire_value():
    client = _client("hEA7OEshlx")
    client.state.fan_level_raw = 4
    assert client.fan_level == FanLevel.MAX


def test_client_fan_level_zultra_out_of_range_is_none():
    client = _client("hEA7OEshlx")
    client.state.fan_level_raw = 0
    assert client.fan_level is None


def test_client_fan_level_is_none_on_legacy_profile():
    client = _client("EHf6cRNRGT")
    client.state.fan_level_raw = 2
    assert client.fan_level is None
