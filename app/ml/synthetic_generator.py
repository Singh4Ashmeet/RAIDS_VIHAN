"""Generate Day 2 training data from realistic RAID Nexus correlations."""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.config import CITY_TO_CODE, TRAINING_DATA_PATH_ENV_VAR

DEFAULT_OUTPUT_PATH = Path(__file__).with_name("training_data.csv")


def get_output_path() -> Path:
    """Return the active training-data CSV path, honoring test/runtime overrides."""

    return Path(os.getenv(TRAINING_DATA_PATH_ENV_VAR, str(DEFAULT_OUTPUT_PATH))).expanduser()


def _traffic_multiplier(random_source: random.Random, hour_of_day: int) -> float:
    if 8 <= hour_of_day <= 10 or 17 <= hour_of_day <= 20:
        return round(random_source.uniform(1.8, 2.5), 3)
    if 1 <= hour_of_day <= 5:
        return round(random_source.uniform(1.0, 1.2), 3)
    return round(random_source.uniform(1.2, 1.8), 3)


def _severity_label(
    complaint_cardiac: int,
    complaint_trauma: int,
    complaint_respiratory: int,
    sos_mode: int,
    patient_age: int,
    patient_count: int,
) -> int:
    if complaint_cardiac and patient_age > 60:
        label = random.choice([2, 3])
    elif complaint_cardiac:
        label = random.choice([1, 2, 3])
    elif complaint_trauma:
        label = 2 if patient_count > 1 else random.choice([1, 2])
    elif complaint_respiratory:
        label = random.choice([2, 3])
    else:
        label = random.choice([0, 1, 2])
    if sos_mode:
        label = min(label + 1, 3)
    return label


def generate_training_data(row_count: int = 10_000) -> pd.DataFrame:
    """Create a synthetic training dataset and write it to CSV."""

    random_source = random.Random(42)
    np_random = np.random.default_rng(42)
    output_path = get_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cities = list(CITY_TO_CODE)
    records: list[dict[str, float | int]] = []

    for _ in range(row_count):
        city = random_source.choice(cities)
        city_encoded = CITY_TO_CODE[city]
        hour_of_day = random_source.randint(0, 23)
        is_weekend = random_source.choice([0, 1])

        complaint_type = random_source.choices(
            ["cardiac", "trauma", "respiratory", "other"],
            weights=[30, 25, 20, 25],
            k=1,
        )[0]
        complaint_cardiac = 1 if complaint_type == "cardiac" else 0
        complaint_trauma = 1 if complaint_type == "trauma" else 0
        complaint_respiratory = 1 if complaint_type == "respiratory" else 0
        sos_mode = random_source.choice([0, 1])
        patient_age = random_source.randint(1, 90)
        patient_count = random_source.randint(1, 8)
        severity_label = _severity_label(
            complaint_cardiac,
            complaint_trauma,
            complaint_respiratory,
            sos_mode,
            patient_age,
            patient_count,
        )
        incident_severity_score = [0.3, 0.5, 0.8, 1.0][severity_label]

        occupancy_pct = random_source.uniform(40.0, 95.0)
        er_wait_minutes = random_source.randint(5, 60)
        if is_weekend:
            occupancy_pct = max(40.0, occupancy_pct - 5.0)
            er_wait_minutes = min(60, er_wait_minutes + 5)
        incoming_patient_count = random_source.randint(0, 10)
        total_icu_beds = random_source.randint(8, 20)
        icu_beds_available = random_source.randint(0, total_icu_beds)
        intake_delay = (
            2.0
            + (occupancy_pct * 0.12)
            + (er_wait_minutes * 0.2)
            + (incoming_patient_count * 0.8)
            + (incident_severity_score * 6.0)
        )
        if occupancy_pct > 80:
            intake_delay += random_source.uniform(10.0, 25.0)
        intake_delay += float(np_random.normal(0, 0.1))
        intake_delay = round(min(max(intake_delay, 2.0), 45.0), 2)

        base_eta_minutes = round(random_source.uniform(3.0, 30.0), 2)
        traffic_multiplier = _traffic_multiplier(random_source, hour_of_day)
        distance_km = round(random_source.uniform(0.5, 25.0), 2)
        ambulance_type = random_source.choice([0, 1])
        eta_drift_factor = traffic_multiplier
        if traffic_multiplier > 2.0:
            eta_drift_factor += random_source.uniform(0.3, 0.6)
        if ambulance_type == 1:
            eta_drift_factor *= 0.95
        actual_eta_minutes = (base_eta_minutes * eta_drift_factor) + float(np_random.normal(0, 0.1))
        actual_eta_minutes = round(max(actual_eta_minutes, base_eta_minutes), 2)

        records.append(
            {
                "complaint_cardiac": complaint_cardiac,
                "complaint_trauma": complaint_trauma,
                "complaint_respiratory": complaint_respiratory,
                "sos_mode": sos_mode,
                "patient_age": patient_age,
                "patient_count": patient_count,
                "severity_label": severity_label,
                "occupancy_pct": round(occupancy_pct, 2),
                "er_wait_minutes": er_wait_minutes,
                "icu_beds_available": icu_beds_available,
                "incoming_patient_count": incoming_patient_count,
                "incident_severity_score": incident_severity_score,
                "hour_of_day": hour_of_day,
                "is_weekend": is_weekend,
                "actual_intake_delay_minutes": intake_delay,
                "base_eta_minutes": base_eta_minutes,
                "traffic_multiplier": traffic_multiplier,
                "distance_km": distance_km,
                "ambulance_type": ambulance_type,
                "city_encoded": city_encoded,
                "actual_eta_minutes": actual_eta_minutes,
            }
        )

    frame = pd.DataFrame.from_records(records)
    frame.to_csv(output_path, index=False)
    return frame


def main() -> None:
    """Generate the training data CSV from the command line."""

    dataset = generate_training_data()
    print(f"Generated {len(dataset)} rows at {get_output_path()}")


if __name__ == "__main__":
    main()
