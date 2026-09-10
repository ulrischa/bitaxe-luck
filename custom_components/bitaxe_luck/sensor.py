"""Sensor platform for Bitaxe Luck."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BitaxeConfigEntry
from .calculations import (
    api_number,
    best_share_expected_hours,
    bits_to_block,
    block_chance_24h_ppm,
    block_chance_for_work_ppm,
    block_distance_factor,
    efficiency_j_th,
    expected_block_years,
    expected_median_best_difficulty,
    luck_percentile,
    luck_rating,
    luck_ratio_to_median,
    rejected_share_percent,
    work_context,
)
from .entity import BitaxeEntity

ValueFn = Callable[[dict[str, Any]], str | int | float | None]


@dataclass(frozen=True, kw_only=True)
class BitaxeSensorEntityDescription(SensorEntityDescription):
    """Describe a Bitaxe sensor."""

    value_fn: ValueFn


SENSORS: tuple[BitaxeSensorEntityDescription, ...] = (
    BitaxeSensorEntityDescription(
        key="hashrate",
        translation_key="hashrate",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: api_number(data, "hashRate"),
    ),
    BitaxeSensorEntityDescription(
        key="hashrate_1m",
        translation_key="hashrate_1m",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: api_number(data, "hashRate_1m"),
    ),
    BitaxeSensorEntityDescription(
        key="hashrate_10m",
        translation_key="hashrate_10m",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: api_number(data, "hashRate_10m"),
    ),
    BitaxeSensorEntityDescription(
        key="hashrate_1h",
        translation_key="hashrate_1h",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: api_number(data, "hashRate_1h"),
    ),
    BitaxeSensorEntityDescription(
        key="expected_hashrate",
        translation_key="expected_hashrate",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda data: api_number(data, "expectedHashrate"),
    ),
    BitaxeSensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: api_number(data, "power"),
    ),
    BitaxeSensorEntityDescription(
        key="efficiency",
        translation_key="efficiency",
        native_unit_of_measurement="J/TH",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=efficiency_j_th,
    ),
    BitaxeSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: api_number(data, "temp"),
    ),
    BitaxeSensorEntityDescription(
        key="vr_temperature",
        translation_key="vr_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: api_number(data, "vrTemp"),
    ),
    BitaxeSensorEntityDescription(
        key="fan_rpm",
        translation_key="fan_rpm",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: api_number(data, "fanrpm"),
    ),
    BitaxeSensorEntityDescription(
        key="error_percentage",
        translation_key="error_percentage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: api_number(data, "errorPercentage"),
    ),
    BitaxeSensorEntityDescription(
        key="accepted_shares",
        translation_key="accepted_shares",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda data: api_number(data, "sharesAccepted"),
    ),
    BitaxeSensorEntityDescription(
        key="rejected_shares",
        translation_key="rejected_shares",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda data: api_number(data, "sharesRejected"),
    ),
    BitaxeSensorEntityDescription(
        key="rejected_share_percentage",
        translation_key="rejected_share_percentage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=rejected_share_percent,
    ),
    BitaxeSensorEntityDescription(
        key="best_difficulty",
        translation_key="best_difficulty",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: api_number(data, "bestDiff"),
    ),
    BitaxeSensorEntityDescription(
        key="best_session_difficulty",
        translation_key="best_session_difficulty",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: api_number(data, "bestSessionDiff"),
    ),
    BitaxeSensorEntityDescription(
        key="network_difficulty",
        translation_key="network_difficulty",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: api_number(data, "networkDifficulty"),
    ),
    BitaxeSensorEntityDescription(
        key="pool_difficulty",
        translation_key="pool_difficulty",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: api_number(data, "poolDifficulty"),
    ),
    BitaxeSensorEntityDescription(
        key="luck_percentile",
        translation_key="luck_percentile",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:clover",
        value_fn=luck_percentile,
    ),
    BitaxeSensorEntityDescription(
        key="luck_rating",
        translation_key="luck_rating",
        device_class=SensorDeviceClass.ENUM,
        options=["very_unlucky", "unlucky", "normal", "lucky", "very_lucky"],
        icon="mdi:clover",
        value_fn=luck_rating,
    ),
    BitaxeSensorEntityDescription(
        key="luck_ratio",
        translation_key="luck_ratio",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:chart-bell-curve-cumulative",
        value_fn=luck_ratio_to_median,
    ),
    BitaxeSensorEntityDescription(
        key="expected_median_best_difficulty",
        translation_key="expected_median_best_difficulty",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:chart-bell-curve",
        value_fn=expected_median_best_difficulty,
    ),
    BitaxeSensorEntityDescription(
        key="block_distance_factor",
        translation_key="block_distance_factor",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:target",
        value_fn=block_distance_factor,
    ),
    BitaxeSensorEntityDescription(
        key="bits_to_block",
        translation_key="bits_to_block",
        native_unit_of_measurement="bit",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:binary",
        value_fn=bits_to_block,
    ),
    BitaxeSensorEntityDescription(
        key="best_share_expected_hours",
        translation_key="best_share_expected_hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:timer-outline",
        value_fn=best_share_expected_hours,
    ),
    BitaxeSensorEntityDescription(
        key="block_chance_work_ppm",
        translation_key="block_chance_work_ppm",
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        icon="mdi:ticket-percent-outline",
        value_fn=block_chance_for_work_ppm,
    ),
    BitaxeSensorEntityDescription(
        key="block_chance_24h_ppm",
        translation_key="block_chance_24h_ppm",
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        icon="mdi:ticket-percent-outline",
        value_fn=block_chance_24h_ppm,
    ),
    BitaxeSensorEntityDescription(
        key="expected_block_years",
        translation_key="expected_block_years",
        native_unit_of_measurement="a",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:calendar-clock",
        value_fn=expected_block_years,
    ),
    BitaxeSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: api_number(data, "uptimeSeconds"),
    ),
    BitaxeSensorEntityDescription(
        key="total_uptime",
        translation_key="total_uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: api_number(data, "totalUptimeSeconds"),
    ),
    BitaxeSensorEntityDescription(
        key="block_height",
        translation_key="block_height",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: api_number(data, "blockHeight"),
    ),
    BitaxeSensorEntityDescription(
        key="blocks_found",
        translation_key="blocks_found",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda data: api_number(data, "blockFound"),
    ),
    BitaxeSensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        value_fn=lambda data: api_number(data, "wifiRSSI"),
    ),
    BitaxeSensorEntityDescription(
        key="core_voltage",
        translation_key="core_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        value_fn=lambda data: api_number(data, "coreVoltageActual"),
    ),
    BitaxeSensorEntityDescription(
        key="current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        value_fn=lambda data: api_number(data, "current"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BitaxeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bitaxe sensors."""
    async_add_entities(BitaxeSensor(entry, description) for description in SENSORS)


class BitaxeSensor(BitaxeEntity, SensorEntity):
    """One Bitaxe sensor."""

    entity_description: BitaxeSensorEntityDescription

    def __init__(
        self,
        entry: BitaxeConfigEntry,
        description: BitaxeSensorEntityDescription,
    ) -> None:
        """Initialize a sensor."""
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | None:
        """Return the current value."""
        value = self.entity_description.value_fn(self.coordinator.data)
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value

    @property
    def available(self) -> bool:
        """Return whether the coordinator and this field are available."""
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, str | float] | None:
        """Expose the calculation basis only on the luck percentile sensor."""
        if self.entity_description.key != "luck_percentile":
            return None

        context = work_context(self.coordinator.data)
        if context is None:
            return None

        return {
            "calculation_basis": context.basis,
            "hashes_used": context.hashes,
            "best_difficulty_used": context.best_difficulty,
        }
