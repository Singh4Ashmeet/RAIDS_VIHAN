"""Hospital fluctuation helpers for the background simulation."""

from __future__ import annotations

import random

from core.config import ER_WAIT_MAX, ER_WAIT_MIN, HOSPITAL_OCCUPANCY_MAX, HOSPITAL_OCCUPANCY_MIN
from repositories.database import fetch_all, update_record


async def fluctuate_hospitals(random_source: random.Random) -> None:
    """Apply small occupancy and ER wait fluctuations to all hospitals."""

    hospitals = await fetch_all("hospitals")
    for hospital in hospitals:
        occupancy_pct = min(
            HOSPITAL_OCCUPANCY_MAX,
            max(HOSPITAL_OCCUPANCY_MIN, float(hospital["occupancy_pct"]) + random_source.uniform(-2.0, 2.0)),
        )
        er_wait = min(
            ER_WAIT_MAX,
            max(ER_WAIT_MIN, int(hospital["er_wait_minutes"]) + random_source.randint(-3, 3)),
        )
        icu_shift = random_source.choice([-1, 0, 1])
        icu_available = min(
            int(hospital["total_icu_beds"]),
            max(0, int(hospital["icu_beds_available"]) + icu_shift),
        )
        diversion_status = bool(hospital["diversion_status"])
        if diversion_status and occupancy_pct < 88.0:
            diversion_status = False
        acceptance_score = max(0.1, round((1.0 - (occupancy_pct / 100.0)), 3))
        await update_record(
            "hospitals",
            hospital["id"],
            {
                "occupancy_pct": round(occupancy_pct, 2),
                "er_wait_minutes": er_wait,
                "icu_beds_available": icu_available,
                "diversion_status": diversion_status,
                "acceptance_score": acceptance_score,
            },
        )
