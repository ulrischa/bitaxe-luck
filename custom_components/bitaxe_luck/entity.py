"""Base entity for Bitaxe Luck."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BitaxeConfigEntry
from .const import DOMAIN
from .coordinator import BitaxeDataUpdateCoordinator


class BitaxeEntity(CoordinatorEntity[BitaxeDataUpdateCoordinator]):
    """Common entity attached to one Bitaxe device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: BitaxeConfigEntry,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(entry.runtime_data.coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return Bitaxe device metadata."""
        data = self.coordinator.data
        board = data.get("boardVersion")
        asic = data.get("ASICModel")

        if board and asic:
            model = f"{board} ({asic})"
        else:
            model = str(board or asic or "Bitaxe")

        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.unique_id or self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="Bitaxe",
            model=model,
            sw_version=str(data.get("version") or data.get("axeOSVersion") or ""),
            hw_version=str(board or ""),
            configuration_url=self._entry.runtime_data.client.base_url,
        )
