"""Button platform for Bitaxe Luck."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BitaxeConfigEntry
from .api import BitaxeApiError
from .entity import BitaxeEntity


@dataclass(frozen=True, kw_only=True)
class BitaxeButtonEntityDescription(ButtonEntityDescription):
    """Describe one AxeOS action."""

    action: str


BUTTONS: tuple[BitaxeButtonEntityDescription, ...] = (
    BitaxeButtonEntityDescription(
        key="restart",
        translation_key="restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        action="restart",
    ),
    BitaxeButtonEntityDescription(
        key="identify",
        translation_key="identify",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:map-marker-question-outline",
        action="identify",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BitaxeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bitaxe action buttons."""
    async_add_entities(BitaxeButton(entry, description) for description in BUTTONS)


class BitaxeButton(BitaxeEntity, ButtonEntity):
    """One AxeOS command button."""

    entity_description: BitaxeButtonEntityDescription

    def __init__(
        self,
        entry: BitaxeConfigEntry,
        description: BitaxeButtonEntityDescription,
    ) -> None:
        """Initialize a button."""
        super().__init__(entry, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Execute the AxeOS action."""
        try:
            if self.entity_description.action == "restart":
                await self._entry.runtime_data.client.async_restart()
                return

            await self._entry.runtime_data.client.async_identify()
        except BitaxeApiError as err:
            raise HomeAssistantError(str(err)) from err
