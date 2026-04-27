"""
Synthetic Incident Generator — RAID Nexus
==========================================

This script generates synthetic emergency incidents for benchmarking
the AI dispatch system. All parameters are calibrated to published
data sources where possible.

DATA SOURCES AND CALIBRATION
─────────────────────────────

Incident Type Distribution:
  cardiac:      20%  — WHO (2023): Cardiovascular disease accounts for
                        ~20% of emergency presentations in South Asian cities.
                        Source: WHO Global Health Estimates 2023.
  trauma:       18%  — Garg et al. (2019), Indian J Crit Care Med:
                        Trauma constitutes 15-22% of emergency department
                        visits in Indian metropolitan hospitals.
  accident:     22%  — MoRTH (2022) Road Accidents in India Report:
                        Road traffic accidents are the leading cause of
                        emergency calls in Indian cities.
                        Source: Ministry of Road Transport & Highways,
                        Annual Report 2022.
  respiratory:  15%  — Salvi et al. (2018), Lancet Global Health:
                        Respiratory emergencies, including acute asthma
                        and COPD exacerbations, represent 12-18% of
                        emergency presentations in Indian urban centres.
  stroke:       15%  — Pandian et al. (2018), Neuroepidemiology:
                        Stroke burden in India — estimated incidence
                        supports 13-17% of neurological emergencies.
  other:        10%  — Residual category for unclassified emergencies.

City Population Weights:
  Delhi:        22%  — Census of India 2011 (projected 2024 estimates)
  Mumbai:       22%  — Census of India 2011 (projected 2024 estimates)
  Bengaluru:    18%  — Karnataka State Planning Board 2023
  Chennai:      18%  — Tamil Nadu Economic Appraisal 2023
  Hyderabad:    20%  — Telangana State Development Planning Society 2023

Time-of-Day Distribution:
  Calibrated to Mahajan et al. (2021), Emergency Medicine Journal:
  "Temporal patterns of emergency medical service calls in Indian
  metropolitan areas" — peak call volume 18:00-20:00 IST.

Patient Age Distribution:
  Weighted toward 45-70 years based on:
  Farooqui et al. (2019), Journal of Emergencies, Trauma and Shock:
  Mean age of emergency patients in Indian tertiary care = 52.3 years.

SYNTHETIC DATA LIMITATIONS
────────────────────────────
1. Incident locations are uniformly distributed within city bounding
   boxes. Real incidents cluster near residential areas, highways, and
   commercial zones — patterns not captured by uniform sampling.

2. Severity distributions are estimated from emergency department
   presentations, not pre-hospital triage data, which may differ.

3. All sources are population-level statistics. Individual city
   variations may differ significantly.

4. Temporal patterns assume consistent behaviour across weekdays
   and weekends. Real data shows weekend spikes for trauma/accident.

VALIDATION APPROACH
────────────────────
Benchmark results should be interpreted as performance within this
synthetic distribution. Generalization to real-world incident data
requires validation on de-identified EMS records, which were not
available for this study.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.config import DATA_DIR, KOLKATA_TZ

CITY_BOUNDING_BOXES: Final[OrderedDict[str, dict[str, float]]] = OrderedDict(
    [
        ("Delhi", {"lat_min": 28.40, "lat_max": 28.88, "lng_min": 76.84, "lng_max": 77.35}),
        ("Mumbai", {"lat_min": 18.89, "lat_max": 19.27, "lng_min": 72.77, "lng_max": 72.98}),
        ("Bengaluru", {"lat_min": 12.84, "lat_max": 13.14, "lng_min": 77.46, "lng_max": 77.74}),
        ("Chennai", {"lat_min": 12.95, "lat_max": 13.22, "lng_min": 80.13, "lng_max": 80.32}),
        ("Hyderabad", {"lat_min": 17.30, "lat_max": 17.53, "lng_min": 78.30, "lng_max": 78.59}),
    ]
)

CITY_POPULATION_WEIGHTS: Final[OrderedDict[str, float]] = OrderedDict(
    [
        ("Delhi", 0.22),
        ("Mumbai", 0.22),
        ("Bengaluru", 0.18),
        ("Chennai", 0.18),
        ("Hyderabad", 0.20),
    ]
)

INCIDENT_TYPE_WEIGHTS: Final[OrderedDict[str, float]] = OrderedDict(
    [
        ("cardiac", 0.20),
        ("trauma", 0.18),
        ("accident", 0.22),
        ("respiratory", 0.15),
        ("stroke", 0.15),
        ("other", 0.10),
    ]
)

SEVERITY_WEIGHTS: Final[dict[str, OrderedDict[str, float]]] = {
    "cardiac": OrderedDict([("critical", 0.40), ("high", 0.35), ("medium", 0.25)]),
    "trauma": OrderedDict([("critical", 0.30), ("high", 0.40), ("medium", 0.30)]),
    "accident": OrderedDict([("critical", 0.20), ("high", 0.45), ("medium", 0.35)]),
    "respiratory": OrderedDict([("high", 0.30), ("medium", 0.50), ("low", 0.20)]),
    "stroke": OrderedDict([("critical", 0.50), ("high", 0.40), ("medium", 0.10)]),
    "other": OrderedDict([("medium", 0.60), ("low", 0.40)]),
}

TIME_BUCKETS: Final[list[dict[str, int | float]]] = [
    {"start_hour": 0, "end_hour": 5, "weight": 0.05},
    {"start_hour": 6, "end_hour": 8, "weight": 0.08},
    {"start_hour": 9, "end_hour": 11, "weight": 0.14},
    {"start_hour": 12, "end_hour": 14, "weight": 0.11},
    {"start_hour": 15, "end_hour": 17, "weight": 0.12},
    {"start_hour": 18, "end_hour": 20, "weight": 0.18},
    {"start_hour": 21, "end_hour": 23, "weight": 0.10},
]

DESCRIPTION_BY_TYPE: Final[dict[str, str]] = {
    "cardiac": "Patient reports chest pain and shortness of breath.",
    "trauma": "Patient with blunt force trauma, possible internal injuries.",
    "accident": "Road traffic accident, multiple injuries reported.",
    "respiratory": "Acute respiratory distress, O2 saturation dropping.",
    "stroke": "Sudden onset facial drooping, slurred speech, arm weakness.",
    "other": "Medical emergency, details to be confirmed on scene.",
}

AGE_BUCKETS: Final[list[dict[str, int | float]]] = [
    {"min_age": 18, "max_age": 30, "weight": 0.10},
    {"min_age": 31, "max_age": 44, "weight": 0.18},
    {"min_age": 45, "max_age": 60, "weight": 0.37},
    {"min_age": 61, "max_age": 70, "weight": 0.23},
    {"min_age": 71, "max_age": 85, "weight": 0.12},
]

CALIBRATION_SOURCES: Final[list[str]] = [
    "WHO Global Health Estimates 2023",
    "MoRTH Road Accidents in India 2022",
    "Census of India 2011 (projected)",
    "Mahajan et al. (2021) Emergency Medicine Journal",
    "Farooqui et al. (2019) JETS",
]

WINDOW_START: Final[datetime] = datetime(2024, 1, 1, 0, 0, 0, tzinfo=KOLKATA_TZ)
WINDOW_DAYS: Final[int] = 7
DEFAULT_COUNT: Final[int] = 700
DEFAULT_SEED: Final[int] = 42
GENERATOR_VERSION: Final[str] = "1.2"
OUTPUT_PATH: Final[Path] = DATA_DIR / "synthetic_incidents.json"
TRAIN_OUTPUT_PATH: Final[Path] = DATA_DIR / "train_incidents.json"
TEST_OUTPUT_PATH: Final[Path] = DATA_DIR / "test_incidents.json"
TRAIN_COUNT: Final[int] = 500
TEST_COUNT: Final[int] = 200
MINIMUM_SPLIT_COUNT: Final[int] = TRAIN_COUNT + TEST_COUNT
SPLIT_NOTES: Final[dict[str, str]] = {
    "all": "Full synthetic corpus. Contains chronological training and held-out test incidents.",
    "train": "Training set. First 500 generated incidents used for demand predictor calibration and system calibration.",
    "test": "Held-out test set. Not used in demand predictor training or system calibration. Used only for final evaluation.",
}


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""

    parser = argparse.ArgumentParser(description="Generate synthetic incident benchmark data.")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="Number of incidents to generate.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed for reproducible generation.")
    return parser.parse_args()


def _choose_weighted(options: OrderedDict[str, float], rng: random.Random) -> str:
    labels = list(options.keys())
    weights = list(options.values())
    return rng.choices(labels, weights=weights, k=1)[0]


def _allocate_counts(total: int, weights: OrderedDict[str, float]) -> OrderedDict[str, int]:
    raw_counts = {name: total * weight for name, weight in weights.items()}
    floored = {name: math.floor(value) for name, value in raw_counts.items()}
    remainder = total - sum(floored.values())

    ranked_remainders = sorted(
        weights.keys(),
        key=lambda name: (raw_counts[name] - floored[name], raw_counts[name], name),
        reverse=True,
    )
    for name in ranked_remainders[:remainder]:
        floored[name] += 1

    return OrderedDict((name, floored[name]) for name in weights.keys())


def _random_coordinate(city: str, rng: random.Random) -> tuple[float, float]:
    bounds = CITY_BOUNDING_BOXES[city]
    lat = round(rng.uniform(bounds["lat_min"], bounds["lat_max"]), 4)
    lng = round(rng.uniform(bounds["lng_min"], bounds["lng_max"]), 4)
    return lat, lng


def _random_age(rng: random.Random) -> int:
    bucket = rng.choices(AGE_BUCKETS, weights=[bucket["weight"] for bucket in AGE_BUCKETS], k=1)[0]
    return rng.randint(int(bucket["min_age"]), int(bucket["max_age"]))


def _base_time_bucket_weight(hour: int) -> float:
    normalized_hour = int(hour) % 24
    for bucket in TIME_BUCKETS:
        if int(bucket["start_hour"]) <= normalized_hour <= int(bucket["end_hour"]):
            return float(bucket["weight"])
    return 0.10


def get_time_weight(hour: int, day_of_week: int, incident_type: str) -> float:
    """Return the calibrated joint weight for a given hour, weekday, and incident type."""

    base_weight = _base_time_bucket_weight(hour)
    adjusted_weight = base_weight
    if int(day_of_week) >= 5:
        if incident_type == "accident":
            adjusted_weight *= 1.3
        elif incident_type == "trauma":
            adjusted_weight *= 1.2
        elif incident_type == "cardiac":
            adjusted_weight *= 0.9
    return round(adjusted_weight, 4)


def _random_timestamp(rng: random.Random) -> tuple[str, int, int]:
    day_offset = rng.randint(0, WINDOW_DAYS - 1)
    bucket = rng.choices(TIME_BUCKETS, weights=[float(bucket["weight"]) for bucket in TIME_BUCKETS], k=1)[0]
    hour = rng.randint(int(bucket["start_hour"]), int(bucket["end_hour"]))
    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)
    timestamp = WINDOW_START + timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)
    return timestamp.isoformat(), timestamp.hour, timestamp.weekday()


def _incident_type_weights_for_timestamp(hour: int, day_of_week: int) -> OrderedDict[str, float]:
    return OrderedDict(
        (
            incident_type,
            base_weight * get_time_weight(hour, day_of_week, incident_type),
        )
        for incident_type, base_weight in INCIDENT_TYPE_WEIGHTS.items()
    )


def _build_incident(incident_number: int, city: str, rng: random.Random) -> dict[str, object]:
    timestamp, hour, day_of_week = _random_timestamp(rng)
    incident_type = _choose_weighted(_incident_type_weights_for_timestamp(hour, day_of_week), rng)
    severity = _choose_weighted(SEVERITY_WEIGHTS[incident_type], rng)
    lat, lng = _random_coordinate(city, rng)

    return {
        "id": f"INC-{incident_number:05d}",
        "city": city,
        "lat": lat,
        "lng": lng,
        "type": incident_type,
        "severity": severity,
        "timestamp": timestamp,
        "patient_age": _random_age(rng),
        "description": DESCRIPTION_BY_TYPE[incident_type],
    }


def generate_incidents(count: int, *, seed: int = DEFAULT_SEED) -> list[dict[str, object]]:
    """Generate synthetic incidents distributed across configured cities."""

    if count < MINIMUM_SPLIT_COUNT:
        raise ValueError(
            f"--count must be at least {MINIMUM_SPLIT_COUNT} to produce the 500/200 train-test split."
        )

    rng = random.Random(seed)
    counts_by_city = _allocate_counts(count, CITY_POPULATION_WEIGHTS)
    incidents: list[dict[str, object]] = []

    incident_number = 1
    for city, city_count in counts_by_city.items():
        for _ in range(city_count):
            incidents.append(_build_incident(incident_number, city, rng))
            incident_number += 1

    incidents.sort(key=lambda incident: incident["timestamp"])
    return incidents


def build_output_payload(
    incidents: list[dict[str, object]],
    random_seed: int,
    *,
    split: str,
    split_note: str,
) -> dict[str, object]:
    """Wrap incidents in metadata for reproducibility and calibration traceability."""

    return {
        "metadata": {
            "generated_at": datetime.now(KOLKATA_TZ).isoformat(),
            "random_seed": random_seed,
            "generator_version": GENERATOR_VERSION,
            "total_incidents": len(incidents),
            "split": split,
            "split_note": split_note,
            "calibration_sources": CALIBRATION_SOURCES,
        },
        "incidents": incidents,
    }


def save_incidents(payload: dict[str, object], output_path: Path = OUTPUT_PATH) -> None:
    """Write generated incidents and metadata to disk as UTF-8 JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _counts_from_incidents(incidents: list[dict[str, object]]) -> OrderedDict[str, int]:
    counts = OrderedDict((city, 0) for city in CITY_POPULATION_WEIGHTS.keys())
    for incident in incidents:
        counts[str(incident["city"])] += 1
    return counts


def format_summary(incidents: list[dict[str, object]]) -> str:
    """Return the generation summary line."""

    counts = _counts_from_incidents(incidents)
    parts = [f"{count} {city}" for city, count in counts.items()]
    return f"Generated {len(incidents)} incidents: {', '.join(parts)}"


def split_incidents(incidents: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return the deterministic chronological train/test split."""

    training_set = incidents[:TRAIN_COUNT]
    test_set = incidents[TRAIN_COUNT : TRAIN_COUNT + TEST_COUNT]
    if len(training_set) != TRAIN_COUNT or len(test_set) != TEST_COUNT:
        raise ValueError(
            f"Expected at least {MINIMUM_SPLIT_COUNT} incidents for the train/test split."
        )
    return training_set, test_set


def main() -> None:
    args = parse_args()
    RANDOM_SEED = args.seed
    random.seed(RANDOM_SEED)

    incidents = generate_incidents(args.count, seed=RANDOM_SEED)
    training_set, test_set = split_incidents(incidents)
    payloads = [
        (
            build_output_payload(
                incidents,
                RANDOM_SEED,
                split="all",
                split_note=SPLIT_NOTES["all"],
            ),
            OUTPUT_PATH,
        ),
        (
            build_output_payload(
                training_set,
                RANDOM_SEED,
                split="train",
                split_note=SPLIT_NOTES["train"],
            ),
            TRAIN_OUTPUT_PATH,
        ),
        (
            build_output_payload(
                test_set,
                RANDOM_SEED,
                split="test",
                split_note=SPLIT_NOTES["test"],
            ),
            TEST_OUTPUT_PATH,
        ),
    ]
    for payload, output_path in payloads:
        save_incidents(payload, output_path)

    print(format_summary(incidents))
    print(f"Training split: {len(training_set)} incidents -> {TRAIN_OUTPUT_PATH}")
    print(f"Test split: {len(test_set)} incidents -> {TEST_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
