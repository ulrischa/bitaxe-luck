"""Mining statistics used by Bitaxe Luck."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Mapping

DIFF1_HASHES = float(2**32)
SECONDS_PER_HOUR = 3600.0
SECONDS_PER_DAY = 86400.0
SECONDS_PER_YEAR = 365.2425 * SECONDS_PER_DAY


@dataclass(frozen=True, slots=True)
class WorkContext:
    """Hashing work and the matching best share."""

    hashes: float
    best_difficulty: float
    basis: str


def _number(value: Any) -> float | None:
    """Convert a numeric API value to a finite float."""
    if value is None or isinstance(value, bool):
        return None

    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(result):
        return None
    return result


def api_number(data: Mapping[str, Any], key: str) -> float | None:
    """Return one numeric AxeOS field."""
    value = data.get(key)
    if key in {"bestDiff", "bestSessionDiff", "networkDifficulty", "poolDifficulty"} and isinstance(
        value, str
    ):
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([kKmMgGtTpPeE])\s*", value)
        if match:
            value = float(match[1]) * 1000 ** ("kmgtpe".index(match[2].lower()) + 1)
    return _number(value)


def average_hashrate_ghs(data: Mapping[str, Any]) -> float | None:
    """Return the best available smoothed hashrate in GH/s."""
    for key in ("hashRate_1h", "hashRate_10m", "hashRate_1m", "hashRate"):
        value = api_number(data, key)
        if value is not None and value > 0:
            return value
    return None


def work_context(data: Mapping[str, Any]) -> WorkContext | None:
    """Return lifetime work when possible, otherwise a session estimate."""
    best_lifetime = api_number(data, "bestDiff")
    total_hashes = api_number(data, "totalHashes")

    if (
        best_lifetime is not None
        and best_lifetime > 0
        and total_hashes is not None
        and total_hashes > 0
    ):
        return WorkContext(total_hashes, best_lifetime, "lifetime_total_hashes")

    total_log2_work = api_number(data, "totalLog2Work")
    if (
        best_lifetime is not None
        and best_lifetime > 0
        and total_log2_work is not None
        and 0 < total_log2_work <= 128
    ):
        return WorkContext(
            2.0**total_log2_work,
            best_lifetime,
            "lifetime_log2_work",
        )

    best_session = api_number(data, "bestSessionDiff")
    uptime = api_number(data, "uptimeSeconds")
    hashrate_ghs = average_hashrate_ghs(data)

    if (
        best_session is not None
        and best_session > 0
        and uptime is not None
        and uptime > 0
        and hashrate_ghs is not None
    ):
        hashes = hashrate_ghs * 1_000_000_000.0 * uptime
        if not math.isfinite(hashes):
            return None
        return WorkContext(hashes, best_session, "session_estimate")

    return None


def luck_percentile(data: Mapping[str, Any]) -> float | None:
    """Return percentile rank of the observed best share for the work done.

    A result of 90 means the observed best share is better than the best share
    from roughly 90% of equal-work mining runs.
    """
    context = work_context(data)
    if context is None:
        return None

    rate = context.hashes / (DIFF1_HASHES * context.best_difficulty)
    return 100.0 * math.exp(-rate)


def luck_rating(data: Mapping[str, Any]) -> str | None:
    """Return a compact categorical interpretation of luck percentile."""
    percentile = luck_percentile(data)
    if percentile is None:
        return None
    if percentile < 10:
        return "very_unlucky"
    if percentile < 25:
        return "unlucky"
    if percentile < 75:
        return "normal"
    if percentile < 90:
        return "lucky"
    return "very_lucky"


def expected_median_best_difficulty(data: Mapping[str, Any]) -> float | None:
    """Return the median best difficulty expected for the amount of work done."""
    context = work_context(data)
    if context is None:
        return None
    return context.hashes / (DIFF1_HASHES * math.log(2.0))


def luck_ratio_to_median(data: Mapping[str, Any]) -> float | None:
    """Return observed best difficulty divided by the equal-work median."""
    context = work_context(data)
    median = expected_median_best_difficulty(data)
    if context is None or median is None or median <= 0:
        return None
    return context.best_difficulty / median


def block_distance_factor(data: Mapping[str, Any]) -> float | None:
    """Return network difficulty divided by lifetime best difficulty."""
    best = api_number(data, "bestDiff")
    network = api_number(data, "networkDifficulty")
    if best is None or network is None or best <= 0 or network <= 0:
        return None
    return network / best


def bits_to_block(data: Mapping[str, Any]) -> float | None:
    """Return additional lucky binary bits needed to reach block difficulty."""
    factor = block_distance_factor(data)
    if factor is None:
        return None
    if factor <= 1:
        return 0.0
    return math.log2(factor)


def best_share_expected_hours(data: Mapping[str, Any]) -> float | None:
    """Return mean waiting time for a share at least as good as lifetime best."""
    best = api_number(data, "bestDiff")
    hashrate_ghs = average_hashrate_ghs(data)
    if best is None or best <= 0 or hashrate_ghs is None:
        return None

    hashes_per_second = hashrate_ghs * 1_000_000_000.0
    return best * DIFF1_HASHES / hashes_per_second / SECONDS_PER_HOUR


def block_chance_for_work_ppm(data: Mapping[str, Any]) -> float | None:
    """Return block probability for completed work in parts per million."""
    context = work_context(data)
    network = api_number(data, "networkDifficulty")
    if context is None or network is None or network <= 0:
        return None

    rate = context.hashes / (DIFF1_HASHES * network)
    return 1_000_000.0 * (-math.expm1(-rate))


def block_chance_24h_ppm(data: Mapping[str, Any]) -> float | None:
    """Return current 24-hour block probability in parts per million."""
    network = api_number(data, "networkDifficulty")
    hashrate_ghs = average_hashrate_ghs(data)
    if network is None or network <= 0 or hashrate_ghs is None:
        return None

    hashes = hashrate_ghs * 1_000_000_000.0 * SECONDS_PER_DAY
    rate = hashes / (DIFF1_HASHES * network)
    return 1_000_000.0 * (-math.expm1(-rate))


def expected_block_years(data: Mapping[str, Any]) -> float | None:
    """Return mean waiting time for a block at the current hashrate."""
    network = api_number(data, "networkDifficulty")
    hashrate_ghs = average_hashrate_ghs(data)
    if network is None or network <= 0 or hashrate_ghs is None:
        return None

    hashes_per_second = hashrate_ghs * 1_000_000_000.0
    return network * DIFF1_HASHES / hashes_per_second / SECONDS_PER_YEAR


def efficiency_j_th(data: Mapping[str, Any]) -> float | None:
    """Return current electrical efficiency in J/TH."""
    power = api_number(data, "power")
    hashrate = api_number(data, "hashRate")
    if power is None or hashrate is None or power < 0 or hashrate <= 0:
        return None
    return power / (hashrate / 1000.0)


def rejected_share_percent(data: Mapping[str, Any]) -> float | None:
    """Return rejected shares as a percentage of resolved shares."""
    accepted = api_number(data, "sharesAccepted")
    rejected = api_number(data, "sharesRejected")
    if accepted is None or rejected is None or accepted < 0 or rejected < 0:
        return None

    total = accepted + rejected
    if total <= 0:
        return 0.0
    return 100.0 * rejected / total


# Created for Uli: keep statistical calculations independent from Home Assistant UI code.
