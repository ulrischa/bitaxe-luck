"""Constants for the Bitaxe Luck integration."""

from homeassistant.const import Platform

DOMAIN = "bitaxe_luck"

DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 300

CONF_SCAN_INTERVAL = "scan_interval"

API_TIMEOUT = 10

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]
