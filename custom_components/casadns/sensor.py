from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    ATTR_PUBLIC_IPV4,
    ATTR_PUBLIC_IPV6,
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
        CasaDNSIPv4Sensor(manager, entry),
        CasaDNSIPv6Sensor(manager, entry),
    ]
    async_add_entities(entities)


class BaseCasaDNSSensor(SensorEntity):
    """Base class for CasaDNS sensors."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:ip-outline"

    def __init__(self, manager, entry: ConfigEntry) -> None:
        self._manager = manager
        self._entry = entry

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes shared across CasaDNS sensors."""
        attrs: dict[str, Any] = {}

        if self._manager.last_ipv4:
            attrs[ATTR_PUBLIC_IPV4] = self._manager.last_ipv4
        if self._manager.last_ipv6:
            attrs[ATTR_PUBLIC_IPV6] = self._manager.last_ipv6
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
        """Return device info so the sensors are grouped under one CasaDNS device."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "CasaDNS",
            "manufacturer": "EMTRONIC",
            "model": "CasaDNS DDNS",
        }


class CasaDNSIPv4Sensor(BaseCasaDNSSensor):
    """Sensor that exposes the current public IPv4 used by CasaDNS."""

    _attr_translation_key = "public_ipv4"

    def __init__(self, manager, entry: ConfigEntry) -> None:
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_public_ipv4"

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""

        def _handle_update() -> None:
            self.async_write_ha_state()

        self._manager.register_listener(_handle_update)
        self.async_write_ha_state()

    @property
    def native_value(self) -> Any:
        """Return the current public IPv4."""
        return self._manager.last_ipv4


class CasaDNSIPv6Sensor(BaseCasaDNSSensor):
    """Sensor that exposes the current public IPv6 used by CasaDNS."""

    _attr_translation_key = "public_ipv6"

    def __init__(self, manager, entry: ConfigEntry) -> None:
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_public_ipv6"

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""

        def _handle_update() -> None:
            self.async_write_ha_state()

        self._manager.register_listener(_handle_update)
        self.async_write_ha_state()

    @property
    def native_value(self) -> Any:
        """Return the current public IPv6."""
        return self._manager.last_ipv6
