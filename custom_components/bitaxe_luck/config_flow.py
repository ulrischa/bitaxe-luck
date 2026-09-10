"""Config flow for Bitaxe Luck."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    BitaxeApiClient,
    BitaxeConnectionError,
    BitaxeInvalidResponseError,
)
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _normalize_host_and_port(raw_host: str, form_port: int) -> tuple[str, int]:
    """Accept HTTP URLs and IP addresses without accepting credentials or paths."""
    import re
    from ipaddress import ip_address

    value = raw_host.strip()
    if not value or not 1 <= form_port <= 65535 or any(c.isspace() for c in value):
        raise ValueError("Invalid host or port")
    if "://" not in value:
        try:
            return str(ip_address(value.strip("[]"))), form_port
        except ValueError:
            value = "http://" + value
    parsed = urlsplit(value)
    if (
        parsed.scheme.lower() != "http"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Enter an HTTP host without credentials, query or API path")
    host = parsed.hostname.lower()
    try:
        ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host):
            raise ValueError("Invalid hostname") from None
    port = parsed.port if parsed.port is not None else form_port
    if not 1 <= port <= 65535:
        raise ValueError("Invalid port")
    return host, port


def _identity(info: dict[str, Any], host: str) -> str:
    """Return the most stable identifier exposed by AxeOS."""
    mac = str(info.get("macAddr") or "").strip().lower()
    if mac:
        return mac
    return host.lower()


def _title(info: dict[str, Any], host: str) -> str:
    """Return a friendly entry title."""
    hostname = str(info.get("hostname") or "").strip()
    if hostname:
        return hostname

    board = str(info.get("boardVersion") or "").strip()
    if board:
        return f"Bitaxe {board}"

    return f"Bitaxe {host}"


async def _validate(
    flow: ConfigFlow,
    host: str,
    port: int,
) -> dict[str, Any]:
    """Connect to AxeOS and return system info."""
    client = BitaxeApiClient(
        async_get_clientsession(flow.hass),
        host,
        port,
    )
    return await client.async_get_system_info()


def _connection_schema(
    suggested: dict[str, Any] | None = None,
) -> vol.Schema:
    """Return the connection form schema."""
    values = suggested or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST,
                default=values.get(CONF_HOST, ""),
            ): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.TEXT,
                    autocomplete="url",
                )
            ),
            vol.Required(
                CONF_PORT,
                default=int(values.get(CONF_PORT, DEFAULT_PORT)),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=65535,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


class BitaxeLuckConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Bitaxe Luck configuration."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Set up one Bitaxe."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                host, port = _normalize_host_and_port(
                    str(user_input[CONF_HOST]),
                    int(user_input[CONF_PORT]),
                )
                info = await _validate(self, host, port)
            except ValueError:
                errors["base"] = "invalid_host"
            except BitaxeConnectionError:
                errors["base"] = "cannot_connect"
            except BitaxeInvalidResponseError:
                errors["base"] = "invalid_response"
            except Exception:
                _LOGGER.exception("Unexpected error while validating Bitaxe")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(_identity(info, host))
                self._abort_if_unique_id_configured()
                for other in self._async_current_entries():
                    if (other.data.get(CONF_HOST), other.data.get(CONF_PORT)) == (host, port):
                        return self.async_abort(reason="already_configured")

                return self.async_create_entry(
                    title=_title(info, host),
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        "identity_source": "mac"
                        if str(info.get("macAddr") or "").strip()
                        else "host",
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Allow changing the host or port."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                host, port = _normalize_host_and_port(
                    str(user_input[CONF_HOST]),
                    int(user_input[CONF_PORT]),
                )
                info = await _validate(self, host, port)
            except ValueError:
                errors["base"] = "invalid_host"
            except BitaxeConnectionError:
                errors["base"] = "cannot_connect"
            except BitaxeInvalidResponseError:
                errors["base"] = "invalid_response"
            except Exception:
                _LOGGER.exception("Unexpected error while reconfiguring Bitaxe")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(_identity(info, host))
                host_identity = entry.data.get("identity_source") == "host" or (
                    "identity_source" not in entry.data
                    and str(entry.unique_id).lower() == str(entry.data[CONF_HOST]).lower()
                )
                if host_identity:
                    # Uli: preserve existing entity identifiers when a legacy host changes.
                    for other in self._async_current_entries():
                        if other.entry_id != entry.entry_id and (
                            other.unique_id == _identity(info, host)
                            or (other.data.get(CONF_HOST), other.data.get(CONF_PORT))
                            == (host, port)
                        ):
                            return self.async_abort(reason="already_configured")
                else:
                    self._abort_if_unique_id_mismatch()

                return self.async_update_reload_and_abort(
                    entry,
                    title=_title(info, host),
                    data_updates={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        "identity_source": "host" if host_identity else "mac",
                    },
                )

        suggested = dict(entry.data)
        if user_input:
            suggested.update(user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(suggested),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Return the options flow."""
        return BitaxeLuckOptionsFlow()


class BitaxeLuckOptionsFlow(OptionsFlowWithReload):
    """Configure non-connection options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = int(
            self.config_entry.options.get(
                CONF_SCAN_INTERVAL,
                DEFAULT_SCAN_INTERVAL,
            )
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=5,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    )
                }
            ),
        )
