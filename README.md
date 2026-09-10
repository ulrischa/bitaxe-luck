<p align="center"><img src="assets/icon.png" alt="Bitaxe Luck" width="144"></p>

# Bitaxe Luck

A local Home Assistant custom integration for Bitaxe miners running AxeOS. Monitor your miner, compare your best share with the work performed, and build a dashboard with standard Home Assistant cards.

**Luck is a statistical comparison, not progress towards winning a Bitcoin block. Every new hash is an independent attempt.**

## Features

- UI configuration: enter a host/IP and port; one device per entry, multiple miners supported.
- One shared local `/api/system/info` request every 30 seconds; configurable from 10 to 300 seconds.
- Hashrate and averages, power, efficiency, temperatures, fan speed, errors, shares, difficulty and diagnostic sensors.
- Luck percentile, luck relative to the median, block difficulty ratio, logarithmic difficulty gap, expected waiting times and block probabilities.
- Mining pause/resume switch, restart and identify buttons where supported by firmware.
- English and German entity names and setup dialogs.
- Included integration icon and dashboard examples; no custom dashboard cards required.

## Requirements

- Home Assistant **2026.9 or later** is the supported baseline.
- A Bitaxe running compatible AxeOS with a reachable local HTTP API.
- Home Assistant must be able to reach the miner, normally on port 80. A browser working on your phone does not prove connectivity from Home Assistant.

Firmware fields vary. Missing statistics become unavailable rather than being invented. Current numeric difficulty values and legacy strings such as `38.11M` are supported. Full lifetime luck requires `bestDiff` plus `totalHashes` or `totalLog2Work`. Older firmware can use an approximate session calculation if `bestSessionDiff`, uptime and hashrate are available.

## Installation

### HACS custom repository

1. Open HACS, select the three-dot menu, then **Custom repositories**.
2. Add `https://github.com/ulrischa/bitaxe-luck` with type **Integration**.
3. Find **Bitaxe Luck** in HACS and download it.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration → Bitaxe Luck**.
6. Enter your miner's IP/hostname and port, normally `80`.

This repository is prepared for installation as a HACS custom repository. It is not claimed to be listed in the default HACS catalog.

### Manual installation

1. Download this repository using **Code → Download ZIP** and extract it.
2. Copy the entire `custom_components/bitaxe_luck` directory into your Home Assistant configuration directory:

   ```text
   /config/custom_components/bitaxe_luck/manifest.json
   /config/custom_components/bitaxe_luck/__init__.py
   /config/custom_components/bitaxe_luck/brand/icon.png
   ...
   ```

   `manifest.json` must be directly inside `bitaxe_luck`, not inside another nested project directory.
3. Restart Home Assistant, then add **Bitaxe Luck** under **Settings → Devices & services**.

No package include or `configuration.yaml` entry is required. If you previously installed the YAML package, remove its configuration to avoid duplicate sensors. Existing custom-integration users can replace the integration directory and restart; the domain and entity unique-ID scheme remain unchanged.

Use **Reconfigure** on the integration entry to change its address and **Configure** to change polling frequency. Reserve the miner's IP in your router. Devices without a MAC address in their API use a host-based identity; when reconfiguring those, make sure the address still belongs to the same physical miner.

## Activate the dashboard

The integration creates entities. It does **not** automatically create a dashboard.

1. Open the Bitaxe device under **Settings → Devices & services** and inspect its entity IDs. You can also find them under **Developer tools → States**.
2. Open [examples/dashboard.yaml](examples/dashboard.yaml). This is a complete dashboard configuration with `views:` at the top.
3. Replace every sample entity ID with the actual ID from your installation. Names depend on the device name and the language used when entities were created; replacing only a prefix may not be enough.
4. Under **Settings → Dashboards**, create a new empty dashboard named **Bitaxe** and open it.
5. Select **Edit dashboard → three-dot menu → Raw configuration editor**. Replace the new dashboard's content with the adapted YAML and save.

Use an empty dashboard so you do not overwrite existing cards. Do not paste the entire file into a manual-card editor. For adding a card to an existing dashboard, copy only an individual item under `cards:` (starting with `type:`). A German version is available at [examples/dashboard_de.yaml](examples/dashboard_de.yaml).

The dashboard includes a large luck gauge, key statistics, mining control and separate history charts. History fills as Home Assistant records new values; the integration does not import AxeOS's older history. The icon is bundled under `brand/` for Home Assistant's integration UI.

## Understanding the statistics

| Metric | Meaning |
| --- | --- |
| Luck percentile | How the observed best share ranks among hypothetical mining runs with the same amount of hash work. Higher means luckier. |
| Luck vs median | Observed best difficulty divided by the median best difficulty expected for the same work. `1` is the median. |
| Block distance factor | Current network difficulty divided by lifetime best difficulty. Smaller is closer in difficulty, not cumulative progress. |
| Bits to block | `max(0, log2(network difficulty / best difficulty))`. A logarithmic difficulty ratio, not a literal count of missing zero bits in your hash. |
| Expected interval for best share | Mean waiting time for a share at least as difficult as your lifetime best, at the selected smoothed hashrate. |
| Equivalent block chance for work done | Hypothetical chance for that amount of work at **today's network difficulty**, not the true historical probability across difficulty changes. |
| Block chance per 24 h | Hypothetical probability over 24 hours at the selected hashrate and unchanged network difficulty. |
| Expected block interval | Statistical mean, not a deadline or prediction for your next block. |

The luck gauge uses these descriptive bands: below 10 very unlucky, 10–25 unlucky, 25–75 normal, 75–90 lucky, and 90–100 very lucky. A percentile of 90 means a better best share than approximately 90% of equal-work runs; it does not mean a 90% chance of a block.

Probability sensors use **ppm** to make tiny values readable: `1 ppm = 0.0001% = one in a million`. Hashrates are reported in GH/s (`1,000 GH/s = 1 TH/s`). Efficiency is J/TH; lower is better at a comparable operating point.

### Calculation and data basis

Let `N` be the number of hashes, `D` the observed best share difficulty, `Dn` network difficulty, and `H` hashrate in hashes per second. Using the conventional mining approximation `K = 2^32` and a Poisson model:

```text
luck percentile       = 100 × exp(-N / (K × D))
median best difficulty = N / (K × ln(2))
probability of ≥1 block = 1 - exp(-N / (K × Dn))
mean time for ≥D share  = K × D / H
```

The code uses `expm1` for very small probabilities. The `2^32` convention is an approximation to Bitcoin's difficulty-one target; displayed figures are estimates.

The **Luck percentile** entity includes `calculation_basis`, `hashes_used`, and `best_difficulty_used` attributes:

1. `lifetime_total_hashes`: `totalHashes` paired with `bestDiff`.
2. `lifetime_log2_work`: `2^totalLog2Work` paired with `bestDiff`.
3. `session_estimate`: smoothed hashrate × uptime paired only with `bestSessionDiff`.

AxeOS itself estimates cumulative work by integrating measured hashrate. The inspected firmware periodically persists these counters; sudden power loss may lose recent work. A firmware upgrade that introduced work tracking can leave an older best share with a newer work counter. Independent resets or differing counter start dates also invalidate the comparison. The integration cannot reconstruct missing history or detect every such mismatch.

Session estimates use the first positive available average in this order: 1 hour, 10 minutes, 1 minute, instantaneous. Multiplying a recent average by the entire uptime is only a rough estimate: earlier pauses, changing frequency, connection losses and warm-up can distort it. Waiting times and 24-hour forecasts assume continued operation at that selected rate; they may still show an operating-rate forecast while mining is paused. No available matching work/share pair means no luck value.

The ratio to block difficulty uses the **current** network value, not necessarily the network difficulty at the moment a past share was found. There is no fixed network-difficulty constant and no external difficulty service.

## Controls and privacy

Only `/api/system/info` is polled. Pause, resume, restart and identify use their corresponding local `POST /api/system/...` endpoints when you explicitly activate a control. This integration does not change pool credentials, overclocking settings or firmware, and does not make cloud requests.

The mining switch requires a boolean `miningPaused` API field. Firmware without that field leaves it unavailable. Unsupported command endpoints return an error; availability of the identify action varies by firmware. Turning mining off means **pause**, not disconnecting electrical power. Turning it on means **resume**, not proof that the pool is accepting shares.

Keep AxeOS on a trusted local network. This client supports HTTP, not authenticated proxies or HTTPS. API redirects are rejected. No wallet address or API password is needed in this integration's setup dialog.

## Troubleshooting

- **Integration not found:** check the folder layout, restart Home Assistant, refresh the browser, and inspect **Settings → System → Logs** for `bitaxe_luck`.
- **Cannot connect:** check the IP, port, VLAN/firewall rules and reachability from the Home Assistant host.
- **Invalid response:** open `http://YOUR-BITAXE-IP/api/system/info`. It should return a JSON object with mining/device fields. HTML, redirects, a 401/403 restriction, a wrong endpoint or incompatible firmware can all cause this message. It does not prove the IP is wrong. Inspect logs and the actual HTTP response.
- **Only some sensors unavailable:** verify the corresponding fields exist in your firmware. A zero/missing network difficulty prevents block comparisons.
- **Luck jumps after restart/update:** inspect the calculation-basis attributes and the counter limitations above.
- **Dashboard says entity not found:** replace example IDs with your real IDs, including translated names.
- **No icon after updating:** restart Home Assistant and refresh its frontend cache.

When reporting a problem, include Home Assistant and AxeOS versions, the relevant error and a redacted API sample. Remove wallet addresses, pool credentials, Wi-Fi/network identifiers and other personal data before posting.

## Development and verification

Core tests can run with Python 3.12+ and `aiohttp`:

```bash
python -m pip install aiohttp
python -m unittest discover -s tests -v
python -m compileall -q custom_components
```

The CI workflow additionally installs the supported Home Assistant baseline and runs `python tests/ha_smoke.py` against its real imports, entity classes, switch actions and setup flow. The core tests use a local HTTP test server; they never access a real miner. Automated checks do not replace an end-to-end installation and dashboard test with physical hardware.

## Sources

- [AxeOS API definition](https://github.com/bitaxeorg/ESP-Miner/blob/master/main/http_server/openapi.yaml)
- [AxeOS cumulative work implementation](https://github.com/bitaxeorg/ESP-Miner/blob/master/main/system.c)
- [Home Assistant integration manifests](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [Home Assistant local integration brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/)

Independent community project, not an official Bitaxe or Home Assistant integration. MIT license; see [LICENSE](LICENSE).
