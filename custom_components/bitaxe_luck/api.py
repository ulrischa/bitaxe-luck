"""Small asynchronous client for the local AxeOS API."""

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientError, ClientSession


class BitaxeApiError(Exception):
    """Base exception for Bitaxe API errors."""


class BitaxeConnectionError(BitaxeApiError):
    """Raised when the Bitaxe cannot be reached."""


class BitaxeInvalidResponseError(BitaxeApiError):
    """Raised when AxeOS returns an unexpected response."""


class BitaxeApiClient:
    """Client for the local AxeOS HTTP API."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        port: int,
        timeout: int = 10,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self.host = host
        self.port = port
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        """Return the AxeOS base URL."""
        host = f"[{self.host}]" if ":" in self.host and not self.host.startswith("[") else self.host
        return f"http://{host}:{self.port}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        expect_json: bool = False,
    ) -> Any:
        """Perform a bounded, redirect-free API request."""
        url = f"{self.base_url}{path}"

        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.request(
                    method,
                    url,
                    allow_redirects=False,
                ) as response:
                    if response.status < 200 or response.status >= 300:
                        raise BitaxeInvalidResponseError(
                            f"AxeOS returned HTTP {response.status} for {path}"
                        )

                    if not expect_json:
                        await response.read()
                        return None

                    try:
                        payload = await response.json(content_type=None)
                    except (ValueError, TypeError) as err:
                        raise BitaxeInvalidResponseError(
                            f"AxeOS returned invalid JSON for {path}"
                        ) from err

        except TimeoutError as err:
            raise BitaxeConnectionError(f"Timeout while connecting to {self.host}") from err
        except ClientError as err:
            raise BitaxeConnectionError(f"Cannot connect to {self.host}: {err}") from err

        return payload

    async def async_get_system_info(self) -> dict[str, Any]:
        """Return /api/system/info."""
        payload = await self._request(
            "GET",
            "/api/system/info",
            expect_json=True,
        )
        if not isinstance(payload, dict):
            raise BitaxeInvalidResponseError("System info is not a JSON object")

        # These fields are characteristic for AxeOS and prevent accepting an unrelated HTTP endpoint.
        if not (
            any(key in payload for key in ("ASICModel", "boardVersion"))
            and "hashRate" in payload
            and any(key in payload for key in ("bestDiff", "bestSessionDiff"))
        ):
            raise BitaxeInvalidResponseError("Endpoint does not look like AxeOS")

        return payload

    async def async_pause_mining(self) -> None:
        """Pause mining."""
        await self._request("POST", "/api/system/pause")

    async def async_resume_mining(self) -> None:
        """Resume mining."""
        await self._request("POST", "/api/system/resume")

    async def async_restart(self) -> None:
        """Restart the device."""
        await self._request("POST", "/api/system/restart")

    async def async_identify(self) -> None:
        """Trigger the AxeOS identify action."""
        await self._request("POST", "/api/system/identify")
