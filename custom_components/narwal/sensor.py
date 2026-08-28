"""Sensor entities for Narwal robot vacuum."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime, UnitOfArea
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NarwalConfigEntry
from .const import FAN_SPEED_REVERSE
from .coordinator import NarwalCoordinator
from .entity import NarwalEntity
from .narwal_client import RobotActivity
from .narwal_client.const import (
    CONSUMABLE_MAINTAIN_NAMES,
    CONSUMABLE_REPLACE_NAMES,
    MOP_HUMIDITY_NAMES_ZULTRA,
    profile_for,
)

_LOGGER = logging.getLogger(__name__)

STATUS_LABELS: dict[RobotActivity, str] = {
    RobotActivity.UNKNOWN: "Unknown",
    RobotActivity.STANDBY: "Standby",
    RobotActivity.SLEEPING: "Sleeping",
    RobotActivity.CLEANING: "Cleaning",
    RobotActivity.MOPPING: "Mopping",
    RobotActivity.PAUSED: "Paused",
    RobotActivity.RETURNING: "Returning",
    RobotActivity.DOCKING: "Docking",
    RobotActivity.DOCKED: "Docked",
    RobotActivity.CHARGING: "Charging",
    RobotActivity.DOCK_WASHING: "Washing Mop",
    RobotActivity.DOCK_DRYING: "Drying Mop",
    RobotActivity.DOCK_EMPTYING: "Emptying Dustbin",
    RobotActivity.DOCK_DUSTBAG_DRYING: "Drying Dust Bag",
    RobotActivity.DOCK_BUSY: "Dock Busy",
    RobotActivity.UPGRADING: "Upgrading",
    RobotActivity.ERROR: "Error",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NarwalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Narwal sensor entities."""
    coordinator = entry.runtime_data
    entities = [
        NarwalBatterySensor(coordinator),
        NarwalStatusSensor(coordinator),
        NarwalElapsedTimeSensor(coordinator),
        NarwalCleanedAreaSensor(coordinator),
    ]
    # Field 26 (fan level) and the working_status progress/room fields have
    # only been confirmed on the Z Ultra
    if profile_for(coordinator.config_entry.data["product_key"]) == "zultra":
        entities.append(NarwalFanLevelSensor(coordinator))
        entities.append(NarwalCleanProgressSensor(coordinator))
        entities.append(NarwalCurrentRoomSensor(coordinator))
        # base status fields 35/29 and consumable/get_consumable_info
        entities.append(NarwalDustBagHealthSensor(coordinator))
        entities.append(NarwalMopHumiditySensor(coordinator))
        entities.append(NarwalConsumablesSensor(coordinator))
    async_add_entities(entities)


class NarwalBatterySensor(NarwalEntity, SensorEntity):
    """Battery level sensor."""

    _attr_translation_key = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.data['device_name']}_battery"

    @property
    def native_value(self) -> float | None:
        state = self.coordinator.data
        if state is None:
            return None
        return max(0.0, min(100.0, state.battery_level))


class NarwalStatusSensor(NarwalEntity, SensorEntity):
    """Working status sensor."""

    _attr_translation_key = "status"

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.data['device_name']}_status"

    @property
    def available(self) -> bool:
        state = self.coordinator.data
        return super().available and state is not None and state.device_reachable

    @property
    def native_value(self) -> str:
        state = self.coordinator.data
        if state is None:
            return "Unknown"
        return STATUS_LABELS.get(state.activity, "Unknown")

    @property
    def extra_state_attributes(self) -> dict:
        state = self.coordinator.data
        if state is None:
            return {}
        return {
            "activity": state.activity.value,
            "working_status_code": state.working_status.value,
            "state_sub_fields": {str(k): v for k, v in state.state_sub_fields.items()},
            "dock_tasks": [
                {
                    "id": t.task_id,
                    "paused": t.paused,
                    "steps": [{"type": s.step_type, "active": s.active} for s in t.steps],
                }
                for t in state.dock_tasks
            ],
            "is_cleaning": state.is_cleaning,
            "is_paused": state.is_paused,
            "is_returning": state.is_returning,
            "is_docked": state.is_docked,
            "error_code": f"0x{state.error_code:08x}" if state.error_code is not None else None,
            "error_message": state.error_message,
        }


class NarwalElapsedTimeSensor(NarwalEntity, SensorEntity):
    """Time elapsed in the current or most recent cleaning session."""

    _attr_translation_key = "elapsed_time"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.data['device_name']}_elapsed_time"

    @property
    def native_value(self) -> int | None:
        state = self.coordinator.data
        if state is None:
            return None
        return state.elapsed_time


class NarwalCleanedAreaSensor(NarwalEntity, SensorEntity):
    """Area covered in the current or most recent cleaning session."""

    _attr_translation_key = "cleaned_area"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "m²"
    _attr_icon = "mdi:texture-box"

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.data['device_name']}_cleaned_area"

    @property
    def native_value(self) -> float | None:
        state = self.coordinator.data
        if state is None:
            return None
        if state.profile == "zultra":
            # working_status field 2 is already m² (field 13 is a constant
            # dryer time, not an area); None until the first clean is seen
            return state.cleaned_area_m2
        return state.cleaned_area / 10000.0  # cm² to m²


class NarwalFanLevelSensor(NarwalEntity, SensorEntity):
    """Fan level as reported by the robot (base status field 26)."""

    _attr_translation_key = "fan_level"
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.data['device_name']}_fan_level"

    @property
    def native_value(self) -> str | None:
        level = self.coordinator.client.fan_level
        return None if level is None else FAN_SPEED_REVERSE.get(level.value)


class NarwalCleanProgressSensor(NarwalEntity, SensorEntity):
    """Progress of the current or most recent clean (working_status field 1)."""

    _attr_translation_key = "clean_progress"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:progress-check"

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.data['device_name']}_clean_progress"

    @property
    def native_value(self) -> float | None:
        state = self.coordinator.data
        if state is None:
            return None
        return state.clean_progress


class NarwalCurrentRoomSensor(NarwalEntity, SensorEntity):
    """Room the robot is currently cleaning (working_status field 6)."""

    _attr_translation_key = "current_room"
    _attr_icon = "mdi:floor-plan"

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.data['device_name']}_current_room"

    @property
    def native_value(self) -> str | None:
        state = self.coordinator.data
        if state is None:
            return None
        return state.current_room_name

    @property
    def extra_state_attributes(self) -> dict:
        state = self.coordinator.data
        return {"room_id": None if state is None else state.current_room_id}


class NarwalDustBagHealthSensor(NarwalEntity, SensorEntity):
    """Station dust-bag health in percent (base status field 35)."""

    _attr_translation_key = "dust_bag_health"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:heart-pulse"

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.data['device_name']}_dust_bag_health"

    @property
    def native_value(self) -> float | None:
        state = self.coordinator.data
        return None if state is None else state.dust_bag_health


class NarwalMopHumiditySensor(NarwalEntity, SensorEntity):
    """Mop humidity as reported by the robot (base status field 29, 1-based)."""

    _attr_translation_key = "mop_humidity"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(MOP_HUMIDITY_NAMES_ZULTRA.values())
    _attr_icon = "mdi:water-percent"

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.data['device_name']}_mop_humidity"

    @property
    def native_value(self) -> str | None:
        state = self.coordinator.data
        if state is None or state.mop_humidity_raw is None:
            return None
        # an unmapped value must not be returned: ENUM sensors reject it
        return MOP_HUMIDITY_NAMES_ZULTRA.get(state.mop_humidity_raw)

    @property
    def extra_state_attributes(self) -> dict:
        state = self.coordinator.data
        return {"raw": None if state is None else state.mop_humidity_raw}


class NarwalConsumablesSensor(NarwalEntity, SensorEntity):
    """Number of consumables the robot says need maintenance or replacement."""

    _attr_translation_key = "consumables_attention"
    _attr_icon = "mdi:wrench-clock"

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.data['device_name']}_consumables_attention"
        )

    @property
    def native_value(self) -> int | None:
        state = self.coordinator.data
        if state is None:
            return None
        return len(state.consumables_maintain) + len(state.consumables_replace)

    @property
    def extra_state_attributes(self) -> dict:
        state = self.coordinator.data
        if state is None:
            return {"maintain": [], "replace": []}
        return {
            "maintain": [
                CONSUMABLE_MAINTAIN_NAMES.get(i, f"Item {i}") for i in state.consumables_maintain
            ],
            "replace": [
                CONSUMABLE_REPLACE_NAMES.get(i, f"Item {i}") for i in state.consumables_replace
            ],
        }
