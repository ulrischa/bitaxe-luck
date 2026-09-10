"""Switch platform for Bitaxe Luck."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BitaxeConfigEntry
from .api import BitaxeApiError
from .entity import BitaxeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BitaxeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the mining switch."""
    async_add_entities([BitaxeMiningSwitch(entry)])


class BitaxeMiningSwitch(BitaxeEntity, SwitchEntity):
    """Pause or resume mining without cutting power."""

    _attr_translation_key = "mining"
    _attr_icon = "mdi:pickaxe"

    def __init__(self, entry: BitaxeConfigEntry) -> None:
        """Initialize the mining switch."""
        super().__init__(entry, "mining")

    @property
    def available(self) -> bool:
        """Return whether miningPaused is supported."""
        return super().available and isinstance(self.coordinator.data.get("miningPaused"), bool)

    @property
    def is_on(self) -> bool | None:
        """Return True when the miner is actively mining."""
        paused = self.coordinator.data.get("miningPaused")
        if not isinstance(paused, bool):
            return None
        return not bool(paused)

    async def async_turn_on(self, **kwargs) -> None:
        """Resume mining."""
        try:
            await self._entry.runtime_data.client.async_resume_mining()
        except BitaxeApiError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Pause mining."""
        try:
            await self._entry.runtime_data.client.async_pause_mining()
        except BitaxeApiError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()
