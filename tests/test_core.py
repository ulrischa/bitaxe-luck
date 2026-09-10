"""Regression tests for Uli's Bitaxe Luck integration; no miner is contacted."""

import ast
import importlib.util
import json
import math
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import ClientSession, web

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "bitaxe_luck"


def load(name):
    spec = importlib.util.spec_from_file_location(name, COMPONENT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


calc = load("calculations")
api = load("api")
# Test the real pure input-validation function without importing Home Assistant.
tree = ast.parse((COMPONENT / "config_flow.py").read_text())
node = next(
    n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_normalize_host_and_port"
)

namespace = {"urlsplit": urlsplit}
exec(compile(ast.Module(body=[node], type_ignores=[]), "config_flow.py", "exec"), namespace)
normalize = namespace["_normalize_host_and_port"]


class CalculationTests(unittest.TestCase):
    def test_equal_work_median_is_fifty_percent(self):
        hashes = 1e17
        best = hashes / (2**32 * math.log(2))
        data = {"totalHashes": hashes, "bestDiff": best}
        self.assertAlmostEqual(calc.luck_percentile(data), 50)
        self.assertAlmostEqual(calc.luck_ratio_to_median(data), 1)

    def test_better_share_increases_luck_more_work_decreases_it(self):
        data = {"totalHashes": 1e17, "bestDiff": 38_106_036}
        rank = calc.luck_percentile(data)
        self.assertGreater(calc.luck_percentile(dict(data, bestDiff=76_212_072)), rank)
        self.assertLess(calc.luck_percentile(dict(data, totalHashes=2e17)), rank)

    def test_session_never_uses_lifetime_best(self):
        data = {
            "bestDiff": 1e12,
            "bestSessionDiff": 1e6,
            "uptimeSeconds": 86400,
            "hashRate_1h": 1000,
        }
        context = calc.work_context(data)
        self.assertEqual(context.best_difficulty, 1e6)
        self.assertEqual(context.hashes, 8.64e16)
        self.assertEqual(context.basis, "session_estimate")
        del data["bestSessionDiff"]
        self.assertIsNone(calc.work_context(data))

    def test_lifetime_and_log2_agree(self):
        data = {"totalHashes": 2**60, "bestDiff": 1e8}
        other = {"totalLog2Work": 60, "bestDiff": 1e8}
        self.assertEqual(calc.luck_percentile(data), calc.luck_percentile(other))

    def test_example_and_units(self):
        data = {
            "bestDiff": 38_106_036.488423,
            "networkDifficulty": 127_450_789_715_843,
            "hashRate_1h": 1070,
        }
        self.assertAlmostEqual(calc.block_distance_factor(data), 3344635, delta=100)
        self.assertAlmostEqual(calc.best_share_expected_hours(data), 42.49, delta=0.02)
        self.assertAlmostEqual(calc.bits_to_block(data), 21.67, delta=0.01)
        self.assertGreater(calc.block_chance_24h_ppm(data), 0)
        self.assertLess(calc.block_chance_24h_ppm(data), 1)
        self.assertAlmostEqual(calc.efficiency_j_th({"power": 18, "hashRate": 1000}), 18)

    def test_invalid_and_missing_numbers(self):
        for value in (None, True, "nonsense", float("nan"), float("inf"), 10**1000):
            self.assertIsNone(calc.api_number({"bestDiff": value}, "bestDiff"))
        for data in ({}, {"bestDiff": 0, "totalHashes": 1}, {"bestDiff": 1, "totalHashes": -1}):
            self.assertIsNone(calc.luck_percentile(data))
        self.assertIsNone(calc.rejected_share_percent({"sharesAccepted": -1, "sharesRejected": 2}))

    def test_legacy_difficulty_suffixes(self):
        self.assertEqual(calc.api_number({"bestDiff": "38.11 M"}, "bestDiff"), 38_110_000)
        self.assertEqual(
            calc.api_number({"networkDifficulty": "127.45T"}, "networkDifficulty"), 127.45e12
        )
        self.assertIsNone(calc.api_number({"power": "18M"}, "power"))

    def test_tiny_probability_preserves_precision(self):
        result = calc.block_chance_for_work_ppm(
            {"totalHashes": 1, "bestDiff": 1, "networkDifficulty": 1e14}
        )
        self.assertGreater(result, 0)
        self.assertAlmostEqual(result / (1e6 / (2**32 * 1e14)), 1)


class HostTests(unittest.TestCase):
    def test_valid_hosts(self):
        for host, expected in [
            ("192.168.1.50", ("192.168.1.50", 80)),
            ("http://bitaxe.local:8080/", ("bitaxe.local", 8080)),
            ("bitaxe.local:8080", ("bitaxe.local", 8080)),
            ("[::1]", ("::1", 80)),
            ("::1", ("::1", 80)),
        ]:
            self.assertEqual(normalize(host, 80), expected)

    def test_reject_invalid_hosts(self):
        for host in (
            "",
            "https://bitaxe.local",
            "http://u:p@bitaxe.local",
            "http://bitaxe.local/api/system/info",
            "http://bitaxe.local?x=1",
            "http://bitaxe.local#x",
            "hello world",
            "bitaxe.local:0",
            "bitaxe.local:65536",
        ):
            with self.subTest(host=host), self.assertRaises(ValueError):
                normalize(host, 80)


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.payload = {"ASICModel": "BM1370", "bestDiff": 123, "hashRate": 1070}
        self.status = 200
        self.html = False
        self.seen = []

        async def handler(request):
            self.seen.append((request.method, request.path))
            if self.html:
                return web.Response(text="<html>AxeOS</html>")
            return web.json_response(self.payload, status=self.status)

        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", handler)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.session = ClientSession()
        self.client = api.BitaxeApiClient(
            self.session, "127.0.0.1", site._server.sockets[0].getsockname()[1]
        )

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()

    async def test_valid_and_legacy_device(self):
        self.assertEqual((await self.client.async_get_system_info())["hashRate"], 1070)
        self.payload = {"boardVersion": "601", "bestSessionDiff": "1M", "hashRate": 0}
        self.assertEqual(await self.client.async_get_system_info(), self.payload)

    async def test_reject_unrelated_html_and_http_errors(self):
        for payload in ([], {"bestDiff": 1}, {"hashRate": 1, "bestDiff": 1}):
            self.payload = payload
            with self.assertRaises(api.BitaxeInvalidResponseError):
                await self.client.async_get_system_info()
        self.html = True
        with self.assertRaises(api.BitaxeInvalidResponseError):
            await self.client.async_get_system_info()
        self.html = False
        for status in (302, 401, 404, 500):
            self.status = status
            with self.assertRaises(api.BitaxeInvalidResponseError):
                await self.client.async_get_system_info()

    async def test_actions_use_correct_methods(self):
        for action in ("pause_mining", "resume_mining", "restart", "identify"):
            await getattr(self.client, "async_" + action)()
        self.assertEqual(
            self.seen,
            [("POST", "/api/system/" + x) for x in ("pause", "resume", "restart", "identify")],
        )

    async def test_timeout(self):
        self.client._timeout = 0
        with self.assertRaises(api.BitaxeConnectionError):
            await self.client.async_get_system_info()


class MetadataTests(unittest.TestCase):
    def test_translation_keys_match(self):
        strings = json.loads((COMPONENT / "strings.json").read_text())

        def keys(value):
            return {k: keys(v) if isinstance(v, dict) else None for k, v in value.items()}

        for filename in ("en.json", "de.json"):
            self.assertEqual(
                keys(strings), keys(json.loads((COMPONENT / "translations" / filename).read_text()))
            )


if __name__ == "__main__":
    unittest.main()
