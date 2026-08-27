from narwal_client.models import parse_protobuf_fields
from narwal_client.zultra import (
    STEP_CLEAN, STEP_DUSTBAG_DRY, STEP_DUST_EMPTY, STEP_MOP_DRY, STEP_MOP_WASH,
    STEP_QUEUED, STEP_RETURN, STEP_SESSION, active_dock_step, newest_task_last_step,
    parse_dock_tasks,
)
from tests.fixtures import zultra_payloads as P


def _field46(payload: bytes) -> bytes:
    return parse_protobuf_fields(payload)[46]


def test_mop_washing_has_two_tasks_with_wash_active_and_dustbag_paused():
    tasks = parse_dock_tasks(_field46(P.MOP_WASHING))
    by_id = {t.task_id: t for t in tasks}
    assert set(by_id) == {940, 909}
    wash = by_id[940]
    assert [s.step_type for s in wash.steps] == [STEP_SESSION, STEP_MOP_WASH]
    assert wash.steps[1].active is True
    assert wash.paused is False
    assert by_id[909].steps[0].step_type == STEP_DUSTBAG_DRY
    assert by_id[909].paused is True


def test_single_task_is_parsed_even_when_not_a_list():
    tasks = parse_dock_tasks(_field46(P.DUST_EMPTYING))
    assert len(tasks) == 1
    assert tasks[0].task_id == 945
    assert tasks[0].steps[0].step_type == STEP_DUST_EMPTY


def test_idle_marker_yields_no_tasks():
    assert parse_dock_tasks(_field46(P.STANDBY_DOCKED)) == []


def test_none_and_garbage_are_safe():
    assert parse_dock_tasks(None) == []
    assert parse_dock_tasks(b"\xff\xff") == []


def test_active_dock_step_prefers_last_step_of_unpaused_task():
    assert active_dock_step(parse_dock_tasks(_field46(P.MOP_DRYING))) == STEP_MOP_DRY
    assert active_dock_step(parse_dock_tasks(_field46(P.MOP_WASHING))) == STEP_MOP_WASH
    assert active_dock_step(parse_dock_tasks(_field46(P.DUSTBAG_DRYING))) == STEP_DUSTBAG_DRY
    assert active_dock_step(parse_dock_tasks(_field46(P.DUST_EMPTYING))) == STEP_DUST_EMPTY


def test_queued_and_clean_tasks_are_not_dock_steps():
    assert active_dock_step(parse_dock_tasks(_field46(P.VACUUM_CLEANING_FAN_MAX))) is None
    assert active_dock_step(parse_dock_tasks(_field46(P.STANDBY_DOCKED))) is None


def test_newest_task_last_step_uses_highest_task_id_paused_or_not():
    assert newest_task_last_step(parse_dock_tasks(_field46(P.COMBO_STARTING))) == STEP_QUEUED
    assert newest_task_last_step(parse_dock_tasks(_field46(P.COMBO_CLEANING))) == STEP_CLEAN
    assert newest_task_last_step(parse_dock_tasks(_field46(P.COMBO_RETURNING_TO_WASH))) == STEP_RETURN
    # task 984 is paused here but is still the newest task
    assert newest_task_last_step(parse_dock_tasks(_field46(P.PAUSED_ON_DOCK_WITH_ERROR))) == STEP_MOP_WASH
    assert newest_task_last_step(parse_dock_tasks(_field46(P.STANDBY_DOCKED))) is None
    assert newest_task_last_step([]) is None
