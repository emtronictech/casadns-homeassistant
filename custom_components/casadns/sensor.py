from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ATTR_PUBLIC_IP

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CasaDNS sensors from a config entry."""
    manager = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        CasaDNSPublicIPSensor(manager, entry),
    ]
    async_add_entities(entities)

class CasaDNSPublicIPSensor(SensorEntity):
    """Sensor that exposes the current public IP used by CasaDNS."""

    _attr_has_entity_name = True
    _attr_name = "CasaDNS Public IP"
    _attr_icon = "mdi:ip-outline"

    def __init__(self, manager, entry: ConfigEntry) -> None:
        self._manager = manager
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_public_ip"

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""

        def _handle_update() -> None:
            # Called from manager when IP changes
            self.async_write_ha_state()

        # Register listener with manager
        self._manager.register_listener(_handle_update)

        # Initial state write
        self.async_write_ha_state()

    @property
    def native_value(self) -> Any:
        """Return the current public IP."""
        return self._manager.last_ip

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        attrs: dict[str, Any] = {}
        if self._manager.last_ip:
            attrs[ATTR_PUBLIC_IP] = self._manager.last_ip
        return attrs
