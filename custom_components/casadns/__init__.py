from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable

from aiohttp.client_exceptions import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import aiohttp_client, event
from homeassistant.loader import async_get_integration
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

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, user_agent: str) -> None:
        self.hass = hass
        self.entry = entry
        self._ua = user_agent

        # Merge data + options (options override data)
        cfg = dict(entry.data)
        cfg.update(entry.options or {})

        self._domains: str = cfg.get(CONF_DOMAINS, entry.data[CONF_DOMAINS])
        self._token: str = cfg.get(CONF_TOKEN, entry.data[CONF_TOKEN])
        self._interval_minutes: int = cfg.get(CONF_INTERVAL, DEFAULT_INTERVAL)

        self._unsub_timer = None

        # Last known IP (IPv6 if available, otherwise IPv4)
        self._last_ip: str | None = None

        # Last CasaDNS call info
        self._last_status: int | None = None
        self._last_error: str | None = None
        self._last_updated: datetime | None = None
        self._status: str | None = None

        self._listeners: list[Callable[[], None]] = []

    @property
    def last_ip(self) -> str | None:
        """Return last known public IP (IPv6 preferred, otherwise IPv4)."""
        return self._last_ip

    @property
    def last_status(self) -> int | None:
        """Return last HTTP status of CasaDNS call."""
        return self._last_status

    @property
    def last_error(self) -> str | None:
        """Return last error message, if any."""
        return self._last_error

    @property
    def last_updated(self) -> datetime | None:
        """Return datetime of last CasaDNS check."""
        return self._last_updated

    @property
    def status(self) -> str | None:
        """Return current CasaDNS status."""
        return self._status

    def as_dict(self) -> dict[str, Any]:
        """Return current CasaDNS state as a dictionary."""
        return {
            "status": self._status,
            "public_ip": self._last_ip,
            "last_status": self._last_status,
            "last_error": self._last_error,
            "last_updated": (
                self._last_updated.isoformat()
                if self._last_updated is not None
                else None
            ),
            "domains": self._domains,
            "interval_minutes": self._interval_minutes,
        }

    def register_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register a callback to be called when data changes."""
        self._listeners.append(callback)

        def remove_listener() -> None:
            """Remove a registered listener."""
            if callback in self._listeners:
                self._listeners.remove(callback)
                
        return remove_listener

    async def async_start(self) -> None:
        """Start periodic update task."""
        interval = timedelta(minutes=self._interval_minutes)
        self._unsub_timer = event.async_track_time_interval(
            self.hass, self._async_timer_callback, interval
        )

        # Initial run at startup
        await self.async_update_dns(force=True)

    def _notify_listeners(self) -> None:
        """Notify registered listeners that CasaDNS state changed."""
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error in CasaDNS listener callback")

    async def async_stop(self) -> None:
        """Stop periodic update task."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    async def _async_timer_callback(self, now) -> None:
        """Timer callback: check IP and update CasaDNS if needed."""
        await self.async_update_dns(force=False)

    async def async_update_dns(self, force: bool = False) -> None:
        """Check current public IP and call CasaDNS if changed or forced."""
        current_ip = await self._async_get_public_ip()
        
        if current_ip is None:
            self._last_status = None
            self._status = "ip_error"
    
            if self._last_error is None:
                self._last_error = "Could not determine public IP"

            self._last_updated = dt_util.utcnow()

            _LOGGER.warning(
                "Could not determine public IP (IPv4/IPv6), skipping CasaDNS update"
            )
            
            self._notify_listeners()
            return
    
        if not force and self._last_ip == current_ip:
            self._last_error = None
            self._status = "unchanged"
            self._last_updated = dt_util.utcnow()
    
            _LOGGER.debug(
                "Public IP unchanged (%s), skipping CasaDNS update", current_ip
            )
            
            self._notify_listeners()
            return
    
        old_ip = self._last_ip
        self._last_ip = current_ip
    
        _LOGGER.info("Public IP changed from %s to %s", old_ip, current_ip)
    
        await self._async_call_casadns(ip=current_ip)
        
        self._notify_listeners()
        
    async def _async_get_public_ip(self) -> str | None:
        """Retrieve public IP using api64.ipify.org.

        Returns IPv6 if available, otherwise IPv4.
        """
        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            async with session.get("https://api64.ipify.org", timeout=10) as resp:
                if resp.status != 200:
                    self._last_error = (
                        f"Error getting public IP from api64.ipify.org: HTTP {resp.status}"
                    )
                
                    _LOGGER.warning(
                        "Error getting public IP from api64.ipify.org: HTTP %s",
                        resp.status,
                    )
                    return None
                return (await resp.text()).strip()
        except (ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error getting public IP from api64.ipify.org: %s", err)
            self._last_error = str(err)
            return None

    async def _async_call_casadns(self, ip: str | None) -> None:
        """Perform CasaDNS update call with clear + current IP."""
        session = aiohttp_client.async_get_clientsession(self.hass)
    
        params: dict[str, str] = {
            "domains": self._domains,
            "token": self._token,
            "clear": "true",
        }
    
        if ip:
            params["ip"] = ip
    
        try:
            async with session.get(
                "https://casadns.eu/update",
                params=params,
                timeout=10,
                headers={
                    "Content-Type": "text/html",
                    "User-Agent": self._ua,
                },
            ) as resp:
                text = await resp.text()
                self._last_status = resp.status
                self._last_updated = dt_util.utcnow()
    
                if resp.status != 200:
                    self._status = "update_error"
                    self._last_error = f"CasaDNS update failed: HTTP {resp.status}"
                    _LOGGER.error(
                        "CasaDNS update failed: HTTP %s - %s", resp.status, text
                    )
                else:
                    self._status = "ok"
                    self._last_error = None
                    _LOGGER.debug("CasaDNS update OK: %s", text)
    
        except (ClientError, asyncio.TimeoutError) as err:
            self._status = "update_error"
            self._last_status = None
            self._last_error = str(err)
            self._last_updated = dt_util.utcnow()
            _LOGGER.error("Error calling CasaDNS: %s", err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CasaDNS from a config entry."""
    integration = await async_get_integration(hass, DOMAIN)
    ua = f"Home Assistant/CasaDNS v{integration.version}"
    
    manager = CasaDNSManager(hass, entry, ua)
    await manager.async_start()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = manager

    async def handle_update_now(call: ServiceCall) -> ServiceResponse:
        """Handle manual service call to force an update."""
        await manager.async_update_dns(force=True)
    
        result = manager.as_dict()
        _LOGGER.debug("CasaDNS manual update result: %s", result)
    
        if call.return_response:
            return result
    
        return None

    if not hass.services.has_service(DOMAIN, "update_now"):
        hass.services.async_register(
            DOMAIN,
            "update_now",
            handle_update_now,
            supports_response=SupportsResponse.OPTIONAL,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        entry.add_update_listener(async_reload_entry)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a CasaDNS config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if not unload_ok:
        return False

    manager: CasaDNSManager | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if manager:
        await manager.async_stop()

    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    if hass.services.has_service(DOMAIN, "update_now"):
        hass.services.async_remove(DOMAIN, "update_now")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload CasaDNS config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
