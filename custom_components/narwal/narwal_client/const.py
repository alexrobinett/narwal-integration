"""Protocol constants, enums, and MQTT topic definitions for Narwal vacuum."""

from enum import Enum, IntEnum

MQTT_BROKER = "us-01.mqtt.narwaltech.com"
MQTT_PORT = 8883

COMMAND_RESPONSE_TIMEOUT = 10.0

# --- Command topics (client → robot) ---
TOPIC_CMD_YELL = "common/yell"
TOPIC_CMD_REBOOT = "common/reboot"
TOPIC_CMD_SHUTDOWN = "common/shutdown"
TOPIC_CMD_GET_DEVICE_INFO = "common/get_device_info"
TOPIC_CMD_GET_FEATURE_LIST = "common/get_feature_list"
TOPIC_CMD_GET_BASE_STATUS = "status/get_device_base_status"
TOPIC_CMD_ACTIVE_ROBOT = "common/active_robot_publish"
TOPIC_CMD_NOTIFY_APP_EVENT = "common/notify_app_event"

# Task control
TOPIC_CMD_PAUSE = "task/pause"
TOPIC_CMD_RESUME = "task/resume"
TOPIC_CMD_FORCE_END = "task/force_end"
TOPIC_CMD_CANCEL = "task/cancel"

# Supply/dock
TOPIC_CMD_RECALL = "supply/recall"
TOPIC_CMD_WASH_MOP = "supply/wash_mop"
# Freo Z Ultra: the app's 'Mop washing' (wash then dry); supply/wash_mop is
# NOT_APPLICABLE on this model.
TOPIC_CMD_WASH_AND_DRY_MOP = "supply/wash_and_dry_mop"
TOPIC_CMD_DRY_MOP = "supply/dry_mop"
TOPIC_CMD_DUST_GATHERING = "supply/dust_gathering"

# Cleaning
TOPIC_CMD_START_CLEAN = "clean/start_clean"
TOPIC_CMD_START_PLAN = "clean/plan/start"
TOPIC_CMD_EASY_CLEAN = "clean/easy_clean/start"
TOPIC_CMD_SET_FAN_LEVEL = "clean/set_fan_level"
TOPIC_CMD_SET_MOP_HUMIDITY = "clean/set_mop_humidity"
TOPIC_CMD_GET_CURRENT_TASK = "clean/current_clean_task/get"

# Config
TOPIC_CMD_GET_CONFIG = "config/get"
TOPIC_CMD_SET_CONFIG = "config/set"
TOPIC_CMD_SET_VOLUME = "config/volume/set"

# Consumables
TOPIC_CMD_GET_CONSUMABLE = "consumable/get_consumable_info"
TOPIC_CMD_RESET_CONSUMABLE = "consumable/reset_consumable_info"

# Schedule
TOPIC_CMD_GET_SCHEDULE = "schedule/clean_schedule/get"

# Map
TOPIC_CMD_GET_MAP = "map/get_map"
TOPIC_CMD_GET_ALL_MAPS = "map/get_all_reduced_maps"

# --- Status topics (robot → client, pushed) ---
TOPIC_WORKING_STATUS = "status/working_status"
TOPIC_ROBOT_BASE_STATUS = "status/robot_base_status"
TOPIC_UPGRADE_STATUS = "status/upgrade_status"


class WorkingStatus(IntEnum):
    UNKNOWN = 0
    STANDBY = 1
    PAUSED = 2
    SLEEPING = 3
    CLEANING = 4
    CLEANING_ALT = 5
    RETURNING = 6
    CHARGING = 7
    MOP_WASHING = 8
    MOP_DRYING = 9
    DOCKED = 10
    DUST_COLLECTING = 11
    UPGRADING = 12
    SELF_CHECK = 13
    CHARGED = 14
    ERROR = 99


class RobotActivity(str, Enum):
    """Semantic robot state shared by all profiles; entities read this, not WorkingStatus."""

    UNKNOWN = "unknown"
    STANDBY = "standby"
    SLEEPING = "sleeping"
    CLEANING = "cleaning"
    MOPPING = "mopping"
    PAUSED = "paused"
    RETURNING = "returning"
    DOCKING = "docking"
    DOCKED = "docked"
    CHARGING = "charging"
    DOCK_WASHING = "dock_washing"
    DOCK_DRYING = "dock_drying"
    DOCK_EMPTYING = "dock_emptying"
    DOCK_DUSTBAG_DRYING = "dock_dustbag_drying"
    DOCK_BUSY = "dock_busy"
    UPGRADING = "upgrading"
    ERROR = "error"


# Product keys that use the Freo Z Ultra decoding (see zultra.py).
ZULTRA_PRODUCT_KEYS = frozenset({"hEA7OEshlx"})


def profile_for(product_key: str) -> str:
    return "zultra" if product_key in ZULTRA_PRODUCT_KEYS else "legacy"


LEGACY_ACTIVITY: dict[WorkingStatus, RobotActivity] = {
    WorkingStatus.UNKNOWN: RobotActivity.UNKNOWN,
    WorkingStatus.STANDBY: RobotActivity.STANDBY,
    WorkingStatus.PAUSED: RobotActivity.PAUSED,
    WorkingStatus.SLEEPING: RobotActivity.SLEEPING,
    WorkingStatus.CLEANING: RobotActivity.CLEANING,
    WorkingStatus.CLEANING_ALT: RobotActivity.CLEANING,
    WorkingStatus.RETURNING: RobotActivity.RETURNING,
    WorkingStatus.CHARGING: RobotActivity.CHARGING,
    WorkingStatus.MOP_WASHING: RobotActivity.DOCK_WASHING,
    WorkingStatus.MOP_DRYING: RobotActivity.DOCK_DRYING,
    WorkingStatus.DOCKED: RobotActivity.DOCKED,
    WorkingStatus.DUST_COLLECTING: RobotActivity.DOCK_EMPTYING,
    WorkingStatus.UPGRADING: RobotActivity.UPGRADING,
    WorkingStatus.SELF_CHECK: RobotActivity.STANDBY,
    WorkingStatus.CHARGED: RobotActivity.CHARGING,
    WorkingStatus.ERROR: RobotActivity.ERROR,
}

DOCKED_ACTIVITIES = frozenset({
    RobotActivity.DOCKED, RobotActivity.CHARGING, RobotActivity.DOCK_WASHING,
    RobotActivity.DOCK_DRYING, RobotActivity.DOCK_EMPTYING,
    RobotActivity.DOCK_DUSTBAG_DRYING, RobotActivity.DOCK_BUSY,
})
OFF_DOCK_ACTIVITIES = frozenset({
    RobotActivity.CLEANING, RobotActivity.MOPPING, RobotActivity.PAUSED,
    RobotActivity.RETURNING,
})
# Activities during which the coordinator only needs keepalive polling
IDLE_ACTIVITIES = frozenset({
    RobotActivity.SLEEPING, RobotActivity.DOCKED, RobotActivity.CHARGING,
})


class FanLevel(IntEnum):
    QUIET = 0
    NORMAL = 1
    STRONG = 2
    MAX = 3


class MopHumidity(IntEnum):
    DRY = 0
    NORMAL = 1
    WET = 2


# robot_base_status field 29 on the Freo Z Ultra reports the mop humidity
# 1-based (like the fan level); MopHumidity above is the 0-based command enum.
MOP_HUMIDITY_NAMES_ZULTRA: dict[int, str] = {1: "Dry", 2: "Normal", 3: "Wet"}


# consumable/get_consumable_info item ids (sjmotew PROTOCOL.md):
# ConsumableInfo{1: maintainItems, 2: replaceItems}, both packed varints.
CONSUMABLE_MAINTAIN_NAMES: dict[int, str] = {
    1: "Dust box",
    2: "Dust filter",
    4: "Wash ribs",
    6: "Universal wheel",
    7: "Cliff sensor",
    8: "Side distance sensor",
    9: "Water-tank sponge",
    10: "Anti-winding brush",
    11: "Smart-module sponge",
    20: "Dust container",
}
CONSUMABLE_REPLACE_NAMES: dict[int, str] = {
    1: "Dust filter",
    2: "Mop",
    3: "Side brush",
    4: "Clear-water filter",
    5: "Roller brush",
    6: "Detergent",
    7: "Smart-module filter",
    8: "Dust bag",
    20: "Station bag",
    21: "Silver ions",
    22: "Curing agent",
    23: "Heavy detergent",
    24: "Inner dust box",
}


class CleanMode(IntEnum):
    VACUUM_AND_MOP = 1
    VACUUM_THEN_MOP = 2
    VACUUM_ONLY = 3
    MOP_ONLY = 4


class CommandResult(IntEnum):
    SUCCESS = 1
    NOT_APPLICABLE = 2
    CONFLICT = 3


ROOM_SUB_TYPE_NAMES: dict[int, str] = {
    0: "Room",
    1: "Master Bedroom",
    2: "Bedroom",
    3: "Living Room",
    4: "Kitchen",
    5: "Bathroom",
    6: "Toilet",
    7: "Dining Room",
    8: "Dining Room",
    9: "Balcony",
    10: "Utility Room",
    11: "Study",
    12: "Nursery",
    13: "Recreation Room",
    14: "Storage Room",
    15: "Other",
}


# Upstream issue #4: the Freo Z sends/reports fan levels 1..4 where the
# X Ultra uses 0..3. robot_base_status field 26 reports the same wire value.
SHIFTED_FAN_MODELS = ZULTRA_PRODUCT_KEYS


def fan_wire_value(product_key: str, level: FanLevel) -> int:
    return level.value + 1 if product_key in SHIFTED_FAN_MODELS else level.value


def fan_level_from_wire(product_key: str, raw: int) -> FanLevel | None:
    value = raw - 1 if product_key in SHIFTED_FAN_MODELS else raw
    try:
        return FanLevel(value)
    except ValueError:
        return None
