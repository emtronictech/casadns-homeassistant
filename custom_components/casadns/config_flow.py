from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_DOMAINS,
    CONF_TOKEN,
    CONF_INTERVAL,
    DEFAULT_INTERVAL,
)

def _normalize_domains(raw: str) -> str:
    """Normalize CasaDNS domain labels.

    Input: " user1.casadns.eu , USER2 , user3 "
    Output: "user1,user2,user3"
    """
    parts: list[str] = []
    for item in raw.split(","):
        label = item.strip().lower()
        if not label:
            continue

        if label.endswith(".casadns.eu"):
            label = label[: -len(".casadns.eu")]

        parts.append(label)

    return ",".join(parts)

class CasaDNSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for CasaDNS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            domains = _normalize_domains(user_input[CONF_DOMAINS])

            if not domains:
                errors["base"] = "invalid_domains"
            else:
                return self.async_create_entry(
                    title="CasaDNS",
                    data={
                        CONF_DOMAINS: domains,
                        CONF_TOKEN: user_input[CONF_TOKEN],
                        CONF_INTERVAL: user_input[CONF_INTERVAL],
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_DOMAINS,
                    description={
                        "suggested_value": "user1,user2,user3"
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
