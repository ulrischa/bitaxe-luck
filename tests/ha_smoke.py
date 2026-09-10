"""Import all platforms against real Home Assistant and validate sensor metadata."""

import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeassistant.core import HomeAssistant

from custom_components.bitaxe_luck import button, config_flow, sensor, switch


async def main():
    for name in (
        "api",
        "calculations",
        "config_flow",
        "coordinator",
        "entity",
        "sensor",
        "switch",
        "button",
    ):
        importlib.import_module("custom_components.bitaxe_luck." + name)
    data = {
        "ASICModel": "BM1370",
        "hashRate": 1070,
        "bestDiff": 38106036,
        "bestSessionDiff": 1000000,
        "networkDifficulty": 127.45e12,
        "totalHashes": 1e17,
        "miningPaused": False,
    }
    coordinator = SimpleNamespace(data=data, last_update_success=True)
    client = SimpleNamespace(
        base_url="http://bitaxe.local:80",
        async_resume_mining=AsyncMock(),
        async_pause_mining=AsyncMock(),
    )
    entry = SimpleNamespace(
        unique_id="test-device",
        entry_id="test-entry",
        title="Bitaxe",
        runtime_data=SimpleNamespace(coordinator=coordinator, client=client),
    )
    keys = set()
    translations = json.loads(
        (
            Path(__file__).resolve().parents[1] / "custom_components/bitaxe_luck/strings.json"
        ).read_text()
    )
    for description in sensor.SENSORS:
        assert description.key not in keys
        keys.add(description.key)
        assert description.translation_key in translations["entity"]["sensor"]
        entity = sensor.BitaxeSensor(entry, description)
        value = entity.native_value
        assert entity.available == (value is not None)
        assert entity.device_info["identifiers"] == {("bitaxe_luck", "test-device")}
    mining = switch.BitaxeMiningSwitch(entry)
    assert mining.is_on and mining.available
    coordinator.async_request_refresh = AsyncMock()
    await mining.async_turn_off()
    client.async_pause_mining.assert_awaited_once()
    data["miningPaused"] = True
    assert not mining.is_on
    for description in button.BUTTONS:
        button.BitaxeButton(entry, description)
    hass = HomeAssistant("/tmp/bitaxe-luck-smoke")
    flow = config_flow.BitaxeLuckConfigFlow()
    flow.hass = hass
    flow.context = {"source": "user"}
    with (
        patch.object(config_flow, "_validate", AsyncMock(return_value=data)),
        patch.object(flow, "async_set_unique_id", AsyncMock()),
        patch.object(flow, "_abort_if_unique_id_configured"),
        patch.object(flow, "_async_current_entries", return_value=[]),
    ):
        result = await flow.async_step_user({"host": "bitaxe.local", "port": 80})
        assert result["type"] == "create_entry"
        assert result["data"]["host"] == "bitaxe.local"
    legacy = SimpleNamespace(
        unique_id="old.local", entry_id="legacy", data={"host": "old.local", "port": 80}
    )
    reconfigure = config_flow.BitaxeLuckConfigFlow()
    reconfigure.hass = hass
    reconfigure.context = {"source": "reconfigure"}

    def update_entry(entry, **kwargs):
        entry.data.update(kwargs["data_updates"])
        return {"type": "abort", "reason": "reconfigure_successful"}

    with (
        patch.object(reconfigure, "_get_reconfigure_entry", return_value=legacy),
        patch.object(config_flow, "_validate", AsyncMock(return_value=data)),
        patch.object(reconfigure, "async_set_unique_id", AsyncMock()),
        patch.object(reconfigure, "_async_current_entries", return_value=[]),
        patch.object(
            reconfigure,
            "_abort_if_unique_id_mismatch",
            side_effect=AssertionError("Host identity must survive repeated address changes"),
        ),
        patch.object(reconfigure, "async_update_reload_and_abort", side_effect=update_entry),
    ):
        for host in ("second.local", "third.local"):
            result = await reconfigure.async_step_reconfigure({"host": host, "port": 80})
            assert result["reason"] == "reconfigure_successful"
            assert legacy.data["host"] == host
            assert legacy.data["identity_source"] == "host"
            assert legacy.unique_id == "old.local"
    print(
        f"Home Assistant smoke check passed: {len(keys)} sensors, switch, buttons and config flow"
    )


asyncio.run(main())
