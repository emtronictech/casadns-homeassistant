from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    ATTR_PUBLIC_IP,
    ATTR_LAST_STATUS,
    ATTR_LAST_ERROR,
    ATTR_LAST_UPDATED,
)


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
    _attr_translation_key = "public_ip"
    _attr_icon = "mdi:ip-outline"

    def __init__(self, manager, entry: ConfigEntry) -> None:
        self._manager = manager
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_public_ip"

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""

        def _handle_update() -> None:
            self.async_write_ha_state()

        self._manager.register_listener(_handle_update)
        self.async_write_ha_state()

    @property
    def native_value(self) -> Any:
        """Return the current public IP (IPv6 or IPv4)."""
        return self._manager.last_ip

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        attrs: dict[str, Any] = {}

        if self._manager.last_ip:
            attrs[ATTR_PUBLIC_IP] = self._manager.last_ip
        if self._manager.last_status is not None:
            attrs[ATTR_LAST_STATUS] = self._manager.last_status
        if self._manager.last_error:
            attrs[ATTR_LAST_ERROR] = self._manager.last_error
        if self._manager.last_updated:
            attrs[ATTR_LAST_UPDATED] = dt_util.as_local(
                self._manager.last_updated
            ).isoformat()

        return attrs

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info so the sensor is grouped under one CasaDNS device."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "CasaDNS DDNS",
            "manufacturer": "EMTRONIC",
            "model": "CasaDNS",
        }
