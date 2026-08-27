"""Freo Z Ultra (product key hEA7OEshlx) decoding.

Everything here was derived from a live capture on 2026-08-27; see
docs/narwal-z-ultra-protocol-notes.md in the owner's HA config repo.
Pure functions only: no HA imports, no MQTT.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .const import LEGACY_ACTIVITY, RobotActivity, WorkingStatus

# Base-station task step types (robot_base_status field 46 → task → step field 1)
STEP_CLEAN = 3          # params {1: 1=vacuum-only / 2=mop, 2: ?, 3: passes}
STEP_RETURN = 4         # recall to dock
STEP_SESSION = 9        # first step of every base-station task
STEP_DUST_EMPTY = 12    # "Dock dust emptying"
STEP_QUEUED = 18        # placeholder before the real step starts
STEP_MOP_WASH = 20      # "Mop washing"
STEP_MOP_DRY = 21       # "Drying mop"
STEP_DUSTBAG_DRY = 25   # "Dust bag drying and disinfection" (1 h, auto after emptying)

DOCK_STEPS = frozenset({STEP_DUST_EMPTY, STEP_MOP_WASH, STEP_MOP_DRY, STEP_DUSTBAG_DRY})


@dataclass
class DockStep:
    step_type: int
    active: bool = False
    params: dict = field(default_factory=dict)


@dataclass
class DockTask:
    task_id: int
    steps: list[DockStep] = field(default_factory=list)
    paused: bool = False


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def parse_dock_tasks(raw: bytes | None) -> list[DockTask]:
    """Decode field 46: {1: [task, ...]} where task = {1: id, 2: [step, ...], 3: paused}.

    A single task is encoded as one field-1 entry (not a list); the idle marker
    is a task with no id ({2: {1: 1}}) and is skipped.
    """
    from .models import parse_protobuf_fields, parse_protobuf_repeated

    if not raw:
        return []
    try:
        outer = parse_protobuf_repeated(raw)
    except Exception:
        return []
    tasks: list[DockTask] = []
    for task_raw in outer.get(1, []):
        if not isinstance(task_raw, bytes):
            continue
        tf = parse_protobuf_repeated(task_raw)
        ids = [v for v in tf.get(1, []) if isinstance(v, int)]
        if not ids:
            continue  # idle marker
        task = DockTask(task_id=ids[0], paused=1 in tf.get(3, []))
        for step_raw in tf.get(2, []):
            if not isinstance(step_raw, bytes):
                continue
            sf = parse_protobuf_fields(step_raw)
            step_type = sf.get(1)
            if not isinstance(step_type, int):
                continue
            params = parse_protobuf_fields(sf[2]) if isinstance(sf.get(2), bytes) else {}
            state = parse_protobuf_fields(sf[3]) if isinstance(sf.get(3), bytes) else {}
            task.steps.append(DockStep(step_type=step_type, active=state.get(1) == 1, params=params))
        tasks.append(task)
    return tasks


def active_dock_step(tasks: list[DockTask]) -> int | None:
    """Return the dock step type currently running, if any.

    The current task is the highest-task_id, non-paused entry (older
    unpaused tasks can linger in the list after they finish, superseded by
    a newer one); its last step is the current one (the robot appends
    steps as they start). Only maintenance steps count; cleaning/return/
    queued steps on the current task are not dock activity.
    """
    candidates = [task for task in tasks if not task.paused and task.steps]
    if not candidates:
        return None
    current = max(candidates, key=lambda task: task.task_id)
    last = current.steps[-1]
    return last.step_type if last.step_type in DOCK_STEPS else None


# Coarse state codes in robot_base_status field 3 sub-field 1 as observed on the Z Ultra.
SUB1_STANDBY = 1
SUB1_VACUUMING = 2      # upstream calls this PAUSED; on Z Ultra it is an active vacuum clean
SUB1_MOPPING = 3        # upstream calls this SLEEPING; on Z Ultra it is an active mop clean
SUB1_COMBO_CLEANING = 4   # "vacuum then mop" clean; sub-field 7 is the phase counter (14/13/8 = working, 2 = heading to dock for a mop wash, 4 = at dock)
SUB1_DOCK_ARRIVAL = 10  # sub-field 10: 2 = docking, 1 = docked
SUB1_DOCK_TASKS = 14    # on dock with mop wash/dry running
SUB1_SERVICING = 19     # transitional: returning, docking contact, dust emptying, dust-bag drying

DOCK_STEP_ACTIVITY = {
    STEP_DUST_EMPTY: RobotActivity.DOCK_EMPTYING,
    STEP_MOP_WASH: RobotActivity.DOCK_WASHING,
    STEP_MOP_DRY: RobotActivity.DOCK_DRYING,
    STEP_DUSTBAG_DRY: RobotActivity.DOCK_DUSTBAG_DRYING,
}

_OFF_DOCK = frozenset({
    RobotActivity.CLEANING, RobotActivity.MOPPING, RobotActivity.PAUSED, RobotActivity.RETURNING,
})


@dataclass
class Resolution:
    activity: RobotActivity
    is_docked: bool = False
    is_cleaning: bool = False
    is_paused: bool = False
    is_returning: bool = False


def _dock(activity: RobotActivity) -> Resolution:
    return Resolution(activity=activity, is_docked=True)


def resolve_activity(sub: dict, tasks: list[DockTask], previous: RobotActivity) -> Resolution:
    """Map the Z Ultra state sub-message + task list to a semantic activity.

    `sub` is the parsed field-3 sub-message ({sub_field: int}). `previous` is the
    last resolved activity; it disambiguates sub1=19, which the robot uses both
    for "returning to dock" and for "servicing on the dock".
    """
    s1 = sub.get(1)
    paused = sub.get(2) == 1

    if s1 == SUB1_VACUUMING:
        if paused:
            return Resolution(RobotActivity.PAUSED, is_paused=True)
        return Resolution(RobotActivity.CLEANING, is_cleaning=True)
    if s1 == SUB1_MOPPING:
        if paused:
            return Resolution(RobotActivity.PAUSED, is_paused=True)
        return Resolution(RobotActivity.MOPPING, is_cleaning=True)
    if s1 == SUB1_COMBO_CLEANING:
        if paused:
            return Resolution(RobotActivity.PAUSED, is_paused=True)
        return Resolution(RobotActivity.CLEANING, is_cleaning=True)
    if s1 == SUB1_STANDBY:
        return Resolution(RobotActivity.STANDBY, is_docked=sub.get(3) == 1)
    if s1 == SUB1_DOCK_ARRIVAL:
        if sub.get(10) == 2:
            return Resolution(RobotActivity.DOCKING, is_returning=True)
        if sub.get(10) == 1:
            return _dock(RobotActivity.DOCKED)
        return Resolution(RobotActivity.UNKNOWN)  # unobserved sub-field 10 value
    if s1 == SUB1_SERVICING:
        if sub.get(18) == 1:
            return _dock(RobotActivity.DOCK_EMPTYING)
        if previous is RobotActivity.UNKNOWN:
            # No history (fresh start / reconnect): 19 is ambiguous between
            # returning and on-dock servicing, so do not guess.
            return Resolution(RobotActivity.UNKNOWN)
        if previous in _OFF_DOCK:
            return Resolution(RobotActivity.RETURNING, is_returning=True)
        step = active_dock_step(tasks)
        return _dock(DOCK_STEP_ACTIVITY.get(step, RobotActivity.DOCK_BUSY))
    if s1 == SUB1_DOCK_TASKS:
        step = active_dock_step(tasks)
        return _dock(DOCK_STEP_ACTIVITY.get(step, RobotActivity.CHARGING))

    # Anything else: fall back to upstream's table if the code exists there.
    try:
        legacy = LEGACY_ACTIVITY[WorkingStatus(s1)]
    except (ValueError, KeyError):
        return Resolution(RobotActivity.UNKNOWN)
    if legacy in (RobotActivity.CLEANING,):
        return Resolution(legacy, is_cleaning=True)
    if legacy is RobotActivity.RETURNING:
        return Resolution(legacy, is_returning=True)
    if legacy is RobotActivity.PAUSED:
        return Resolution(legacy, is_paused=True)
    return Resolution(legacy, is_docked=legacy in (
        RobotActivity.DOCKED, RobotActivity.CHARGING, RobotActivity.DOCK_WASHING,
        RobotActivity.DOCK_DRYING, RobotActivity.DOCK_EMPTYING,
    ))
