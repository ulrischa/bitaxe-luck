"""Data coordinator for Bitaxe Luck."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BitaxeApiClient, BitaxeApiError

_LOGGER = logging.getLogger(__name__)


class BitaxeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate one /api/system/info poll for all entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: BitaxeApiClient,
        scan_interval: int,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Bitaxe Luck",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch current AxeOS data."""
        try:
            return await self.client.async_get_system_info()
        except BitaxeApiError as err:
            raise UpdateFailed(str(err)) from err
