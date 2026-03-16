"""Config flow for FortisBC integration."""
from __future__ import annotations

import voluptuous as vol

from fortisbc import FortisbcClient
from fortisbc import FortisbcAuthError

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate_credentials(hass: HomeAssistant, username: str, password: str) -> None:
    """Test credentials by attempting login."""
    client = FortisbcClient(username, password)
    await hass.async_add_executor_job(client.login)


class FortisbcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle FortisBC config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await _validate_credentials(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except FortisbcAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"FortisBC ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
