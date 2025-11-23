from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Callable

from aiohttp.client_exceptions import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import aiohttp_client, event
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_DOMAINS,
    CONF_TOKEN,
    CONF_INTERVAL,
    DEFAULT_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]


class CasaDNSManager:
    """Handle CasaDNS periodic updates and state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        # Merge data + options (options override data)
        cfg = dict(entry.data)
        cfg.update(entry.options or {})

        self._domains: str = cfg.get(CONF_DOMAINS, entry.data[CONF_DOMAINS])
        self._token: str = cfg.get(CONF_TOKEN, entry.data[CONF_TOKEN])
        self._interval_minutes: int = cfg.get(CONF_INTERVAL, DEFAULT_INTERVAL)

        self._unsub_timer = None

        self._last_ip: str | None = None
        self._last_ipv4: str | None = None
        self._last_ipv6: str | None = None

        self._last_status: int | None = None
        self._last_error: str | None = None
        self._last_updated = None  # datetime | None

        self._listeners: list[Callable[[], None]] = []

    @property
    def last_ip(self) -> str | None:
        """Return last primary public IP (IPv4 preferred over IPv6)."""
        return self._last_ip

    @property
    def last_ipv4(self) -> str | None:
        """Return last known public IPv4."""
        return self._last_ipv4

    @property
    def last_ipv6(self) -> str | None:
        """Return last known public IPv6."""
        return self._last_ipv6

    @property
    def last_status(self) -> int | None:
        """Return last HTTP status of CasaDNS call."""
        return self._last_status

    @property
    def last_error(self) -> str | None:
        """Return last error message, if any."""
        return self._last_error

    @property
    def last_updated(self):
        """Return datetime of last CasaDNS call."""
        return self._last_updated

    def register_listener(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called when data changes."""
        self._listeners.append(callback)

    async def async_start(self) -> None:
        """Start periodic update task."""
        interval = timedelta(minutes=self._interval_minutes)
        self._unsub_timer = event.async_track_time_interval(
            self.hass, self._async_timer_callback, interval
        )

        # Initial run at startup
        await self.async_update_dns(force=True)

    async def async_stop(self) -> None:
        """Stop periodic update task."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    async def _async_timer_callback(self, now) -> None:
        """Timer callback: check IP and update CasaDNS if needed."""
        await self.async_update_dns(force=False)

    async def async_update_dns(self, force: bool = False) -> None:
        """Check current public IPv4/IPv6 and call CasaDNS if changed or forced."""
        ipv4, ipv6 = await self._async_get_public_ips()

        if ipv4 is None and ipv6 is None:
            _LOGGER.warning(
                "Could not determine public IPv4 or IPv6, skipping CasaDNS update"
            )
            return

        current_primary = ipv4 or ipv6

        if (
            not force
            and self._last_ipv4 == ipv4
            and self._last_ipv6 == ipv6
        ):
            _LOGGER.debug(
                "Public IPs unchanged (IPv4=%s, IPv6=%s), skipping CasaDNS update",
                ipv4,
                ipv6,
            )
            return

        old_ipv4 = self._last_ipv4
        old_ipv6 = self._last_ipv6

        self._last_ipv4 = ipv4
        self._last_ipv6 = ipv6
        self._last_ip = current_primary

        _LOGGER.info(
            "Public IPs changed from IPv4=%s / IPv6=%s to IPv4=%s / IPv6=%s",
            old_ipv4,
            old_ipv6,
            ipv4,
            ipv6,
        )

        # Notify listeners (sensors) over state-change
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error in CasaDNS listener callback")

        await self._async_call_casadns(ipv4=ipv4, ipv6=ipv6)

    async def _async_get_public_ips(self) -> tuple[str | None, str | None]:
        """Retrieve public IPv4 and IPv6 using external services.

        Returns:
            (ipv4, ipv6) where each can be None if not available.
        """
        session = aiohttp_client.async_get_clientsession(self.hass)

        ipv4: str | None = None
        ipv6: str | None = None

        # IPv4
        try:
            async with session.get("https://ipv4.api.ipify.org", timeout=10) as resp:
                if resp.status == 200:
                    ipv4 = (await resp.text()).strip()
                else:
                    _LOGGER.warning("Error getting public IPv4: HTTP %s", resp.status)
        except (ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error getting public IPv4: %s", err)

        # IPv6
        try:
            async with session.get("https://ipv6.api.ipify.org", timeout=10) as resp:
                if resp.status == 200:
                    ipv6 = (await resp.text()).strip()
                else:
                    _LOGGER.warning("Error getting public IPv6: HTTP %s", resp.status)
        except (ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error getting public IPv6: %s", err)

        return ipv4, ipv6

    async def _async_call_casadns(
        self,
        ipv4: str | None = None,
        ipv6: str | None = None,
    ) -> None:
        """Perform CasaDNS update with clear + IP updates in one call."""
        session = aiohttp_client.async_get_clientsession(self.hass)
    
        base = (
            "https://casadns.eu/update"
            f"?domains={self._domains}"
            f"&token={self._token}"
        )
    
        params: list[str] = []
    
        # Always clear existing A and AAAA
        params.append("clear=true")
    
        # ip= accepts IPv4 or IPv6
        if ipv4:
            params.append(f"ip={ipv4}")
        elif ipv6:
            params.append(f"ip={ipv6}")
    
        # If both available, add ipv6 separately
        if ipv6 and ipv4:
            params.append(f"ipv6={ipv6}")
        elif ipv6 and not ipv4:
            # If only IPv6 exists → ip= already carries IPv6, but ipv6= is optional
            # Using ipv6= improves clarity
            params.append(f"ipv6={ipv6}")
    
        url = base + "&" + "&".join(params)
    
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
                self._last_status = resp.status
                self._last_updated = dt_util.utcnow()
                self._last_error = None
    
                if resp.status != 200:
                    _LOGGER.error(
                        "CasaDNS update failed: HTTP %s - %s",
                        resp.status,
                        text,
                    )
                else:
                    _LOGGER.debug("CasaDNS update OK: %s", text)
    
        except (ClientError, asyncio.TimeoutError) as err:
            self._last_error = str(err)
            _LOGGER.error("Error calling CasaDNS: %s", err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CasaDNS from a config entry."""
    manager = CasaDNSManager(hass, entry)
    await manager.async_start()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = manager

    async def handle_update_now(call: ServiceCall) -> None:
        """Handle manual service call to force an update."""
        await manager.async_update_dns(force=True)

    hass.services.async_register(DOMAIN, "update_now", handle_update_now)

    # Forward to platforms (sensor)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when options are updated
    entry.async_on_unload(
        entry.add_update_listener(async_reload_entry)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a CasaDNS config entry."""
    manager: CasaDNSManager | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if manager:
        await manager.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    hass.services.async_remove(DOMAIN, "update_now")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload CasaDNS config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
