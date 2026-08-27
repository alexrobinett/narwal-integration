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
    async_add_entities([
        NarwalBatterySensor(coordinator),
        NarwalStatusSensor(coordinator),
        NarwalElapsedTimeSensor(coordinator),
        NarwalCleanedAreaSensor(coordinator),
        NarwalFanLevelSensor(coordinator),
    ])


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
