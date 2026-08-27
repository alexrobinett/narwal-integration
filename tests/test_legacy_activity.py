from narwal_client.const import RobotActivity as A, WorkingStatus, profile_for
from narwal_client.models import NarwalState


def test_profile_for():
    assert profile_for("hEA7OEshlx") == "zultra"
    assert profile_for("EHf6cRNRGT") == "legacy"


def test_legacy_profile_maps_working_status_to_activity():
    s = NarwalState()  # profile defaults to legacy
    s.update_base_status(bytes.fromhex("1a020804"))  # field 3 = {1: 4} CLEANING
    assert s.working_status == WorkingStatus.CLEANING
    assert s.activity == A.CLEANING
    assert s.is_cleaning is True and s.is_docked is False
    s.update_base_status(bytes.fromhex("1a02080e"))  # {1: 14} CHARGED
    assert s.activity == A.CHARGING
    assert s.is_docked is True


def test_legacy_paused_disambiguation_matches_upstream():
    s = NarwalState()
    s.update_base_status(bytes.fromhex("1a04080210 01"))  # {1: 2, 2: 1} -> really paused
    assert s.working_status == WorkingStatus.PAUSED
    assert s.activity == A.PAUSED and s.is_paused is True
    s.update_base_status(bytes.fromhex("1a020802"))  # {1: 2}, no flags -> active task
    assert s.working_status == WorkingStatus.CLEANING and s.is_cleaning is True
    s.update_base_status(bytes.fromhex("1a04080238 01"))  # {1: 2, 7: 1} -> returning
    assert s.working_status == WorkingStatus.RETURNING and s.is_returning is True


def test_legacy_payload_without_status_code_keeps_previous_status():
    # Upstream only disambiguated PAUSED when sub-field 1 was present; a
    # battery-only payload must not flip a stale PAUSED into CLEANING.
    s = NarwalState()
    s.update_base_status(bytes.fromhex("1a04080210 01"))  # {1: 2, 2: 1} PAUSED
    s.update_base_status(bytes.fromhex("150000f841"))  # field 2 only (battery 31.0)
    assert s.working_status == WorkingStatus.PAUSED
    assert s.activity == A.PAUSED and s.is_paused is True
    assert s.battery_level == 31.0
