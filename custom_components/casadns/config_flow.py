from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_DOMAINS,
    CONF_TOKEN,
    CONF_INTERVAL,
    DEFAULT_INTERVAL,
)


def _normalize_domains(raw: str) -> str:
    """Normalize CasaDNS domains."""
    parts: list[str] = []

    for item in raw.split(","):
        label = item.strip().lower()
        if not label:
            # Skip empty pieces (e.g. trailing comma)
            continue

        # Strip optional .casadns.eu if user accidentally adds it
        if label.endswith(".casadns.eu"):
            label = label[: -len(".casadns.eu")]

        if label:
            parts.append(label)

    return ",".join(parts)


class CasaDNSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for CasaDNS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_domains = user_input.get(CONF_DOMAINS, "")
            token = user_input.get(CONF_TOKEN)
            interval = user_input.get(CONF_INTERVAL, DEFAULT_INTERVAL)

            normalized_domains = _normalize_domains(raw_domains)

            # Basic validation: at least one non-empty domain
            if not normalized_domains:
                errors["base"] = "invalid_domains"
            elif not token:
                errors["base"] = "invalid_token"

            if not errors:
                return self.async_create_entry(
                    title="CasaDNS",
                    data={
                        CONF_DOMAINS: normalized_domains,
                        CONF_TOKEN: token,
                        CONF_INTERVAL: interval,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_DOMAINS,
                    description={
                        "suggested_value": "domain1,domain2,domain3",
                    },
                ): str,
                vol.Required(CONF_TOKEN): str,
                vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): int,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return CasaDNSOptionsFlowHandler(config_entry)


class CasaDNSOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle CasaDNS options (domains, interval)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize CasaDNS options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the CasaDNS options."""
        errors: dict[str, str] = {}

        # Current values: options override data
        current = dict(self._config_entry.data)
        current.update(self._config_entry.options or {})

        if user_input is not None:
            raw_domains = user_input.get(CONF_DOMAINS, "")
            interval = user_input.get(CONF_INTERVAL, DEFAULT_INTERVAL)

            normalized_domains = _normalize_domains(raw_domains)

            if not normalized_domains:
                errors["base"] = "invalid_domains"

            if not errors:
                # Only store options that can be changed
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_DOMAINS: normalized_domains,
                        CONF_INTERVAL: interval,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_DOMAINS,
                    default=current.get(CONF_DOMAINS, ""),
                ): str,
                vol.Optional(
                    CONF_INTERVAL,
                    default=current.get(CONF_INTERVAL, DEFAULT_INTERVAL),
                ): int,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
