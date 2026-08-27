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
