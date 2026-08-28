"""Binary sensors for Narwal robot vacuum: base-station component states (Freo Z Ultra)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NarwalConfigEntry
from .coordinator import NarwalCoordinator
from .entity import NarwalEntity
from .narwal_client.const import profile_for


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NarwalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Narwal binary sensor entities."""
    coordinator = entry.runtime_data
    # robot_base_status fields 20/21/23/24/39 have only been confirmed on the Z Ultra
    if profile_for(coordinator.config_entry.data["product_key"]) != "zultra":
        return
    async_add_entities(
        [
            NarwalDustBoxSensor(coordinator),
            NarwalDustBagSensor(coordinator),
            NarwalCleanWaterTankSensor(coordinator),
            NarwalSewageTankSensor(coordinator),
            NarwalStationBagSensor(coordinator),
        ]
    )


class NarwalProblemSensor(NarwalEntity, BinarySensorEntity):
    """A station component state enum from robot_base_status: 1 = normal.

    Observed values are 1 (normal) and 2 (abnormal / removed); any value
    other than 1 is reported as a problem. Unavailable while the robot has
    not reported the field (the Z Ultra never sends the dust-bag state).
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _key = ""
    _state_attr = ""

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.data['device_name']}_{self._key}"

    @property
    def _value(self) -> int | None:
        state = self.coordinator.data
        return None if state is None else getattr(state, self._state_attr)

    @property
    def available(self) -> bool:
        return super().available and self._value is not None

    @property
    def is_on(self) -> bool:
        value = self._value
        return value is not None and value != 1

    @property
    def extra_state_attributes(self) -> dict:
        return {"raw_state": self._value}


class NarwalDustBoxSensor(NarwalProblemSensor):
    _attr_translation_key = "dust_box"
    _attr_icon = "mdi:delete-variant"
    _key = "dust_box"
    _state_attr = "dust_box_state"


class NarwalDustBagSensor(NarwalProblemSensor):
    _attr_translation_key = "dust_bag"
    _attr_icon = "mdi:delete-variant"
    _key = "dust_bag"
    _state_attr = "dust_bag_state"


class NarwalCleanWaterTankSensor(NarwalProblemSensor):
    _attr_translation_key = "clean_water_tank"
    _attr_icon = "mdi:water"
    _key = "clean_water_tank"
    _state_attr = "clean_water_state"


class NarwalSewageTankSensor(NarwalProblemSensor):
    _attr_translation_key = "sewage_tank"
    _attr_icon = "mdi:water-off"
    _key = "sewage_tank"
    _state_attr = "sewage_state"


class NarwalStationBagSensor(NarwalProblemSensor):
    _attr_translation_key = "station_bag"
    _attr_icon = "mdi:delete-variant"
    _key = "station_bag"
    _state_attr = "station_bag_state"
