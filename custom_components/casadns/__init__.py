from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from aiohttp.client_exceptions import ClientError

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import aiohttp_client, event

from .const import (
    DOMAIN,
    CONF_DOMAINS,
    CONF_TOKEN,
    CONF_INTERVAL,
    DEFAULT_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class CasaDNSManager:
    """Handle CasaDNS periodic updates."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._domains: str = entry.data[CONF_DOMAINS]
        self._token: str = entry.data[CONF_TOKEN]
        self._interval_minutes: int = entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL)

        self._unsub_timer = None
        self._last_ip: str | None = None

    async def async_start(self) -> None:
        """Start periodic update task."""
        interval = timedelta(minutes=self._interval_minutes)
        self._unsub_timer = event.async_track_time_interval(
            self.hass, self._async_timer_callback, interval
        )

    async def async_stop(self) -> None:
        """Stop periodic update task."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None

    async def _async_timer_callback(self, now) -> None:
        """Timer callback: check IP and update CasaDNS if needed."""
        await self.async_update_dns(force=False)

    async def async_update_dns(self, force: bool = False) -> None:
        """Check current public IP and call CasaDNS if changed or forced."""
        current_ip = await self._async_get_public_ip()
        if current_ip is None:
            _LOGGER.warning("Could not determine public IP, skipping CasaDNS update")
            return

        if not force and self._last_ip == current_ip:
            _LOGGER.debug("Public IP unchanged (%s), skipping CasaDNS update", current_ip)
            return

        _LOGGER.info("Public IP changed from %s to %s, calling CasaDNS", self._last_ip, current_ip)
        self._last_ip = current_ip

        await self._async_call_casadns()

    async def _async_get_public_ip(self) -> str | None:
        """Retrieve public IP using external service."""
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            # Simple plaintext IP service, returns "x.x.x.x"
            async with session.get("https://api.ipify.org", timeout=10) as resp:
                if resp.status != 200:
                    _LOGGER.warning("Error getting public IP: HTTP %s", resp.status)
                    return None
                return (await resp.text()).strip()
        except (ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error getting public IP: %s", err)
            return None

    async def _async_call_casadns(self) -> None:
        """Perform CasaDNS update call."""
        session = aiohttp_client.async_get_clientsession(self.hass)

        url = (
            f"https://casadns.eu/update"
            f"?domains={self._domains}"
            f"&token={self._token}"
        )

        try:
            async with session.get(
                url,
                timeout=10,
                headers={
                    "Content-Type": "text/html",
                    "User-Agent": "Home Assistant CasaDNS",
                },
                ssl=False,
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    _LOGGER.error("CasaDNS update failed: HTTP %s - %s", resp.status, text)
                else:
                    _LOGGER.debug("CasaDNS update OK: %s", text)
        except (ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error calling CasaDNS: %s", err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CasaDNS from a config entry."""
    manager = CasaDNSManager(hass, entry)
    await manager.async_start()

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = manager

    async def handle_update_now(call: ServiceCall) -> None:
        """Handle manual service call to force an update."""
        await manager.async_update_dns(force=True)

    hass.services.async_register(DOMAIN, "update_now", handle_update_now)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a CasaDNS config entry."""
    manager: CasaDNSManager | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if manager:
        await manager.async_stop()

    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    if DOMAIN in hass.services.async_services().get(DOMAIN, {}):
        hass.services.async_remove(DOMAIN, "update_now")

    return True
