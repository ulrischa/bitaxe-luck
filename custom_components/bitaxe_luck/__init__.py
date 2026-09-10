"""Bitaxe Luck integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BitaxeApiClient
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, PLATFORMS
from .coordinator import BitaxeDataUpdateCoordinator


@dataclass(slots=True)
class BitaxeRuntimeData:
    """Runtime objects for one Bitaxe config entry."""

    client: BitaxeApiClient
    coordinator: BitaxeDataUpdateCoordinator


type BitaxeConfigEntry = ConfigEntry[BitaxeRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BitaxeConfigEntry,
) -> bool:
    """Set up Bitaxe Luck from a config entry."""
    session = async_get_clientsession(hass)
    client = BitaxeApiClient(
        session,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
    )
    coordinator = BitaxeDataUpdateCoordinator(
        hass,
        client,
        int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        entry,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = BitaxeRuntimeData(
        client=client,
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: BitaxeConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
