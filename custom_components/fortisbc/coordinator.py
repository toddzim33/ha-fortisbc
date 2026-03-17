"""DataUpdateCoordinator for FortisBC."""
from __future__ import annotations

import logging
from datetime import timedelta

from fortisbc import FortisbcClient
from fortisbc import FortisbcAuthError, FortisbcError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN, UPDATE_INTERVAL_HOURS

_LOGGER = logging.getLogger(__name__)


class FortisbcCoordinator(DataUpdateCoordinator):
    """Manages polling FortisBC and distributing data to sensors."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=UPDATE_INTERVAL_HOURS),
        )
        self._username = entry.data[CONF_USERNAME]
        self._password = entry.data[CONF_PASSWORD]

    async def _async_update_data(self) -> dict:
        """Fetch data from FortisBC portal.

        A fresh client is created per fetch so the TLS session is always
        properly closed, regardless of success or failure.
        """
        def _fetch() -> dict:
            client = FortisbcClient(self._username, self._password)
            try:
                client.login()
                return client.fetch_all()
            finally:
                client.close()

        try:
            return await self.hass.async_add_executor_job(_fetch)
        except FortisbcAuthError as err:
            raise ConfigEntryAuthFailed(err) from err
        except FortisbcError as err:
            raise UpdateFailed(f"FortisBC fetch failed: {err}") from err
