"""Freo Z Ultra (product key hEA7OEshlx) decoding.

Everything here was derived from a live capture on 2026-08-27; see
docs/narwal-z-ultra-protocol-notes.md in the owner's HA config repo.
Pure functions only: no HA imports, no MQTT.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
