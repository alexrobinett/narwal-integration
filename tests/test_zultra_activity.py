import pytest

from narwal_client.const import RobotActivity as A
from narwal_client.models import NarwalState
from tests.fixtures import zultra_payloads as P


def _state(previous: A = A.UNKNOWN) -> NarwalState:
    s = NarwalState(profile="zultra")
    s.activity = previous
    return s


@pytest.mark.parametrize(
    "payload, previous, activity, docked, cleaning",
    [
        (P.MOPPING, A.UNKNOWN, A.MOPPING, False, True),
        (P.DOCKING_TRANSIENT_AFTER_MOP, A.MOPPING, A.RETURNING, False, False),
        (P.ON_DOCK_PREDRY, A.RETURNING, A.DOCK_DRYING, True, False),
        (P.MOP_WASHING, A.DOCK_DRYING, A.DOCK_WASHING, True, False),
        (P.MOP_DRYING, A.DOCK_WASHING, A.DOCK_DRYING, True, False),
        (P.STANDBY_DOCKED, A.DOCK_DRYING, A.STANDBY, True, False),
        (P.DUST_EMPTYING, A.STANDBY, A.DOCK_EMPTYING, True, False),
        (P.DUSTBAG_DRYING, A.DOCK_EMPTYING, A.DOCK_DUSTBAG_DRYING, True, False),
        (P.VACUUM_LEAVING_DOCK, A.DOCK_DUSTBAG_DRYING, A.CLEANING, False, True),
        (P.VACUUM_CLEANING_FAN_MAX, A.CLEANING, A.CLEANING, False, True),
        (P.RETURNING, A.CLEANING, A.RETURNING, False, False),
        (P.DOCKING, A.RETURNING, A.DOCKING, False, False),
        (P.DOCKED_AFTER_RETURN, A.DOCKING, A.DOCKED, True, False),
        # dock servicing resumes after re-dock: same sub as RETURNING but previous was on dock
        (P.DUSTBAG_DRYING, A.DOCKED, A.DOCK_DUSTBAG_DRYING, True, False),
        # "vacuum then mop" combo clean: sub1=4, sub7 is the phase counter
        (P.COMBO_STARTING, A.DOCK_DUSTBAG_DRYING, A.CLEANING, False, True),
        (P.COMBO_CLEANING, A.CLEANING, A.CLEANING, False, True),
        (P.COMBO_RETURNING_TO_WASH, A.CLEANING, A.CLEANING, False, True),
        (P.PAUSED_ON_DOCK_WITH_ERROR, A.CLEANING, A.PAUSED, False, False),
    ],
)
def test_zultra_activity_from_captured_payloads(payload, previous, activity, docked, cleaning):
    s = _state(previous)
    s.update_base_status(payload)
    assert s.activity == activity
    assert s.is_docked is docked
    assert s.is_cleaning is cleaning


def test_returning_flag_and_battery():
    s = _state(A.CLEANING)
    s.update_base_status(P.RETURNING)
    assert s.is_returning is True
    assert s.battery_level == pytest.approx(31.0)


def test_fan_level_raw_is_read_from_field_26():
    s = _state(A.CLEANING)
    s.update_base_status(P.VACUUM_CLEANING_FAN_MAX)
    assert s.fan_level_raw == 4
    s.update_base_status(P.MOPPING)
    assert s.fan_level_raw == 2


def test_dock_tasks_and_sub_fields_are_exposed():
    s = _state(A.DOCK_DRYING)
    s.update_base_status(P.MOP_WASHING)
    assert [t.task_id for t in s.dock_tasks] == [940, 909]
    assert s.state_sub_fields == {1: 14, 12: 3}


def test_unknown_sub1_is_reported_not_invented():
    s = _state(A.STANDBY)
    # hand-built payload: field 3 = {1: 77}
    s.update_base_status(bytes.fromhex("1a02084d"))
    assert s.activity == A.UNKNOWN
    assert s.is_docked is False


def test_status_less_payload_keeps_previous_activity_and_flags():
    s = _state(A.CLEANING)
    s.update_base_status(P.RETURNING)
    assert s.activity == A.RETURNING
    # battery-only frame (field 2 = 31.0, no field 3): state must not change
    s.update_base_status(bytes.fromhex("150000f841"))
    assert s.activity == A.RETURNING
    assert s.is_docked is False
    assert s.is_returning is True
    assert s.battery_level == pytest.approx(31.0)
    # and the hysteresis still works on the next real frame
    s.update_base_status(P.RETURNING)
    assert s.activity == A.RETURNING
    assert s.is_docked is False


def test_sub1_19_with_unknown_previous_is_unknown_not_on_dock():
    # e.g. HA restart while the robot is returning: no history to disambiguate 19
    s = _state(A.UNKNOWN)
    s.update_base_status(P.RETURNING)
    assert s.activity == A.UNKNOWN
    assert s.is_docked is False
    assert s.is_returning is False


def test_sub1_10_with_unobserved_sub10_is_unknown():
    s = _state(A.RETURNING)
    # hand-built payload: field 3 = {1: 10, 10: 3}
    s.update_base_status(bytes.fromhex("1a04080a5003"))
    assert s.activity == A.UNKNOWN
    assert s.is_docked is False
    assert s.is_returning is False


def test_combo_clean_paused_by_base_error_sets_is_paused():
    s = _state(A.CLEANING)
    s.update_base_status(P.PAUSED_ON_DOCK_WITH_ERROR)
    assert s.activity == A.PAUSED
    assert s.is_paused is True
    assert s.is_cleaning is False
    assert s.is_docked is False
