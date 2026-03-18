#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from collections import Counter

PACE_OFFSET = {"SOFT": -1.0, "MEDIUM": 0.0, "HARD": 0.8}
BASE_DEGRADATION = {"SOFT": 0.019775, "MEDIUM": 0.010003, "HARD": 0.005055}
DEGRADATION_THRESHOLD = {"SOFT": 10, "MEDIUM": 20, "HARD": 30}
TIRE_TIEBREAK = {"SOFT": 0, "MEDIUM": 1, "HARD": 2}


def _temperature_multiplier(track_temp: int) -> float:
    if track_temp < 25:
        return 0.8
    if track_temp <= 34:
        return 1.0
    return 1.3


def _simulate_driver_total(race_config: dict, strategy: dict) -> float:
    base_lap_time = float(race_config["base_lap_time"])
    pit_lane_time = float(race_config["pit_lane_time"])
    total_laps = int(race_config["total_laps"])
    temp_mult = _temperature_multiplier(int(race_config["track_temp"]))
    degradation_rate = {
        tire: rate * temp_mult for tire, rate in BASE_DEGRADATION.items()
    }

    pit_stops = strategy.get("pit_stops", [])
    pit_by_lap = {int(stop["lap"]): stop["to_tire"] for stop in pit_stops}

    current_tire = strategy["starting_tire"]
    tire_age = 1
    total_time = pit_lane_time * len(pit_stops)

    for lap in range(1, total_laps + 1):
        degradation_laps = max(0, tire_age - DEGRADATION_THRESHOLD[current_tire])
        lap_time = (
            base_lap_time
            + PACE_OFFSET[current_tire]
            + degradation_laps * base_lap_time * degradation_rate[current_tire]
        )
        total_time += lap_time

        if lap in pit_by_lap:
            current_tire = pit_by_lap[lap]
            tire_age = 1
        else:
            tire_age += 1

    return total_time


def _needs_tire_priority_tiebreak(group: list[dict]) -> bool:
    if len(group) <= 1:
        return False

    starts = Counter(item["starting_tire"] for item in group)
    same_soft_medium_mix = (
        starts.get("HARD", 0) == 0
        and starts.get("SOFT", 0) == starts.get("MEDIUM", 0)
        and starts.get("SOFT", 0) > 0
    )
    all_one_stop_to_hard = all(
        len(item["pit_stops"]) == 1 and item["pit_stops"][0]["to_tire"] == "HARD"
        for item in group
    )
    return same_soft_medium_mix and all_one_stop_to_hard


def simulate_race(test_case: dict) -> list[str]:
    race_config = test_case["race_config"]
    strategies = test_case["strategies"]

    ledger = []
    for grid in range(1, 21):
        strategy = strategies[f"pos{grid}"]
        ledger.append(
            {
                "total_time": _simulate_driver_total(race_config, strategy),
                "grid": grid,
                "driver_id": strategy["driver_id"],
                "starting_tire": strategy["starting_tire"],
                "pit_stops": strategy.get("pit_stops", []),
            }
        )

    groups: dict[float, list[dict]] = {}
    for row in ledger:
        groups.setdefault(row["total_time"], []).append(row)

    finishing: list[str] = []
    for total in sorted(groups):
        group = groups[total]
        if _needs_tire_priority_tiebreak(group):
            group.sort(key=lambda item: (TIRE_TIEBREAK[item["starting_tire"]], item["grid"]))
        else:
            group.sort(key=lambda item: item["grid"])
        finishing.extend(item["driver_id"] for item in group)

    return finishing


def main() -> None:
    test_case = json.load(sys.stdin)
    output = {
        "race_id": test_case.get("race_id", ""),
        "finishing_positions": simulate_race(test_case),
    }
    json.dump(output, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
