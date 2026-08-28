"""Z Ultra base-status station fields: tank/dust/bag states, dust-bag health, mop humidity.

Field names from sjmotew PROTOCOL.md §7, values confirmed on the 2026-08-27
capture: 20 dust-box state, 21 dust-bag state (never sent by this robot),
23 clean-water tank state, 24 sewage tank state, 39 station-bag state (all
enums, 1 = normal), 35 station/dust-bag health % (float32), 29 mop humidity
(1-based on this model: 1 Dry, 2 Normal, 3 Wet).
"""

from narwal_client.models import NarwalState
from tests.fixtures import zultra_payloads as P

STATE_FIELDS = (
    "dust_box_state", "dust_bag_state", "clean_water_state", "sewage_state", "station_bag_state",
)


def _zultra() -> NarwalState:
    return NarwalState(profile="zultra")


def test_defaults_are_unset_before_any_frame():
    s = _zultra()
    for name in STATE_FIELDS:
        assert getattr(s, name) is None
    assert s.dust_bag_health is None
    assert s.mop_humidity_raw is None


def test_healthy_station_frame_reads_all_fields():
    s = _zultra()
    s.update_base_status(P.PAUSED_ON_DOCK_WITH_ERROR)
    assert s.dust_box_state == 1
    assert s.dust_bag_state is None  # field 21 absent on the Z Ultra
    assert s.clean_water_state == 1
    assert s.sewage_state == 1  # error block still latched, tank already back to normal
    assert s.station_bag_state == 1
    assert s.dust_bag_health == 68.3  # float32 68.3136 → 1 dp
    assert s.mop_humidity_raw == 2


def test_sewage_tank_abnormal_frame():
    s = _zultra()
    s.update_base_status(P.SEWAGE_TANK_ABNORMAL)
    assert s.sewage_state == 2
    assert s.clean_water_state == 1
    assert s.dust_box_state == 1
    assert s.station_bag_state == 1


def test_clean_water_tank_removed_frame():
    s = _zultra()
    s.update_base_status(P.CLEAN_WATER_TANK_REMOVED)
    assert s.clean_water_state == 2
    assert s.sewage_state == 1


def test_tank_state_returns_to_normal_on_next_frame():
    s = _zultra()
    s.update_base_status(P.SEWAGE_TANK_ABNORMAL)
    s.update_base_status(P.STANDBY_DOCKED)
    assert s.sewage_state == 1


def test_mop_humidity_is_wet_while_mopping():
    s = _zultra()
    s.update_base_status(P.MOPPING)
    assert s.mop_humidity_raw == 3
    assert s.dust_bag_health == 68.5


def test_absent_fields_read_as_none():
    # hand-built zultra frame carrying only field 3 = {1: 1}: no station fields
    s = _zultra()
    s.update_base_status(P.MOPPING)
    s.update_base_status(bytes.fromhex("1a020801"))
    for name in STATE_FIELDS:
        assert getattr(s, name) is None
    assert s.dust_bag_health is None
    assert s.mop_humidity_raw is None


def test_legacy_profile_never_populates_station_fields():
    s = NarwalState()
    s.update_base_status(P.SEWAGE_TANK_ABNORMAL)
    for name in STATE_FIELDS:
        assert getattr(s, name) is None
    assert s.dust_bag_health is None
    assert s.mop_humidity_raw is None
