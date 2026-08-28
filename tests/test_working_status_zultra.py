"""Z Ultra working_status decode: progress / real area / current room.

Frames captured 2026-08-27 (whole MQTT payload, hex). The leading 0x01 frame
byte mentioned in the brief is not part of these captures — each starts at the
first protobuf tag (0x0d = field 1 fixed32, 0x18 = field 3 varint, 0x58 =
field 11 varint), which is exactly what update_working_status receives.
"""

from narwal_client.models import NarwalState, RoomInfo

# mopping 17:28:04 → prog 92.0, area 5.1948 (float32 0x40a63bcd → 5.19 at 2 dp), elapsed 461, room 1
MOPPING = bytes.fromhex("0d0000b84215cd3ba64018cd03300158901c60990368d08c0178d8049201009a0100")
# vacuum clean 17:46:50 → elapsed 6, room 4 (no prog/area yet)
VACUUM_START = bytes.fromhex("18062a020804300458901c604e68d08c0178d8049201009a0100")
# idle 17:41:08 → none of 1/2/3/6
IDLE = bytes.fromhex("58901c68d08c0178d8049201009a0100")

ROOMS = [RoomInfo(room_id=1, name="Living Room"), RoomInfo(room_id=4, room_sub_type=6)]


def _zultra() -> NarwalState:
    return NarwalState(profile="zultra", rooms=list(ROOMS))


def test_defaults_are_none_before_any_frame():
    s = _zultra()
    assert s.clean_progress is None
    assert s.cleaned_area_m2 is None
    assert s.current_room_id is None
    assert s.current_room_name is None


def test_mopping_frame_decodes_progress_area_elapsed_room():
    s = _zultra()
    s.update_working_status(MOPPING)
    assert s.clean_progress == 92.0
    assert s.cleaned_area_m2 == 5.19
    assert s.elapsed_time == 461
    assert s.current_room_id == 1
    assert s.current_room_name == "Living Room"


def test_idle_frame_latches_session_values_and_clears_room():
    s = _zultra()
    s.update_working_status(MOPPING)
    s.update_working_status(IDLE)
    assert s.clean_progress == 92.0
    assert s.cleaned_area_m2 == 5.19
    assert s.elapsed_time == 461
    assert s.current_room_id is None
    assert s.current_room_name is None


def test_new_clean_resets_progress_and_area():
    s = _zultra()
    s.update_working_status(MOPPING)
    s.update_working_status(IDLE)
    s.update_working_status(VACUUM_START)  # elapsed 6 < 461 → new session
    assert s.clean_progress == 0.0
    assert s.cleaned_area_m2 == 0.0
    assert s.elapsed_time == 6
    assert s.current_room_id == 4
    assert s.current_room_name == "Toilet"


def test_same_session_frame_without_progress_keeps_latched_values():
    # elapsed grows (not a new session) but fields 1/2 are missing: keep values
    s = _zultra()
    s.update_working_status(MOPPING)
    s.update_working_status(bytes.fromhex("18ce03" + "3001" + "58901c"))  # elapsed 462, room 1
    assert s.clean_progress == 92.0
    assert s.cleaned_area_m2 == 5.19
    assert s.elapsed_time == 462
    assert s.current_room_id == 1


def test_unknown_room_id_has_no_name():
    s = _zultra()
    s.update_working_status(bytes.fromhex("1806" + "3009"))  # elapsed 6, room 9
    assert s.current_room_id == 9
    assert s.current_room_name is None


def test_zultra_field13_is_not_treated_as_area():
    s = _zultra()
    s.update_working_status(MOPPING)
    assert s.cleaned_area_m2 == 5.19
    # upstream attribute still mirrors field 13 so legacy consumers are unaffected
    assert s.cleaned_area == 18000


def test_legacy_profile_keeps_upstream_mapping():
    s = NarwalState()
    s.update_working_status(MOPPING)
    assert s.cleaned_area == 18000
    assert s.elapsed_time == 461
    assert s.clean_progress is None
    assert s.cleaned_area_m2 is None
    assert s.current_room_id is None
    assert s.current_room_name is None
