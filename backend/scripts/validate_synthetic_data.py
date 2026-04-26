"""Validate calibrated synthetic incident data against target distributions."""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Final

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import DATA_DIR, KOLKATA_TZ

SYNTHETIC_INCIDENTS_PATH: Final[Path] = DATA_DIR / "synthetic_incidents.json"
VALIDATION_REPORT_PATH: Final[Path] = DATA_DIR / "validation_report.json"
ACCEPTABLE_DEVIATION: Final[float] = 0.05
FAIL_DEVIATION: Final[float] = 0.25
TARGET_AGE_MEAN: Final[float] = 52.3

INCIDENT_TYPE_TARGETS_BASE: Final[OrderedDict[str, float]] = OrderedDict(
    [
        ("cardiac", 0.20),
        ("trauma", 0.18),
        ("accident", 0.22),
        ("respiratory", 0.15),
        ("stroke", 0.15),
        ("other", 0.10),
    ]
)

CITY_TARGETS: Final[OrderedDict[str, float]] = OrderedDict(
    [
        ("Delhi", 0.22),
        ("Mumbai", 0.22),
        ("Bengaluru", 0.18),
        ("Chennai", 0.18),
        ("Hyderabad", 0.20),
    ]
)

TIME_BUCKET_TARGETS_RAW: Final[OrderedDict[str, float]] = OrderedDict(
    [
        ("00:00-05:59", 0.05),
        ("06:00-08:59", 0.08),
        ("09:00-11:59", 0.14),
        ("12:00-14:59", 0.11),
        ("15:00-17:59", 0.12),
        ("18:00-20:59", 0.18),
        ("21:00-23:59", 0.10),
    ]
)

SEVERITY_TARGETS_BY_TYPE: Final[dict[str, OrderedDict[str, float]]] = {
    "cardiac": OrderedDict([("critical", 0.40), ("high", 0.35), ("medium", 0.25)]),
    "trauma": OrderedDict([("critical", 0.30), ("high", 0.40), ("medium", 0.30)]),
    "accident": OrderedDict([("critical", 0.20), ("high", 0.45), ("medium", 0.35)]),
    "respiratory": OrderedDict([("high", 0.30), ("medium", 0.50), ("low", 0.20)]),
    "stroke": OrderedDict([("critical", 0.50), ("high", 0.40), ("medium", 0.10)]),
    "other": OrderedDict([("medium", 0.60), ("low", 0.40)]),
}

WEEKEND_TYPE_MULTIPLIERS: Final[dict[str, float]] = {
    "cardiac": 0.9,
    "trauma": 1.2,
    "accident": 1.3,
    "respiratory": 1.0,
    "stroke": 1.0,
    "other": 1.0,
}

ALL_SEVERITIES: Final[list[str]] = ["critical", "high", "medium", "low"]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _normalize(weights: OrderedDict[str, float]) -> OrderedDict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return OrderedDict((key, 0.0) for key in weights)
    return OrderedDict((key, value / total) for key, value in weights.items())


def _weekend_adjusted_incident_targets() -> OrderedDict[str, float]:
    weekday_fraction = 5 / 7
    weekend_fraction = 2 / 7
    weekend_weights = OrderedDict(
        (
            incident_type,
            base_weight * WEEKEND_TYPE_MULTIPLIERS.get(incident_type, 1.0),
        )
        for incident_type, base_weight in INCIDENT_TYPE_TARGETS_BASE.items()
    )
    normalized_weekend = _normalize(weekend_weights)
    return OrderedDict(
        (
            incident_type,
            (weekday_fraction * base_weight) + (weekend_fraction * normalized_weekend[incident_type]),
        )
        for incident_type, base_weight in INCIDENT_TYPE_TARGETS_BASE.items()
    )


INCIDENT_TYPE_TARGETS: Final[OrderedDict[str, float]] = _weekend_adjusted_incident_targets()
TIME_BUCKET_TARGETS: Final[OrderedDict[str, float]] = _normalize(TIME_BUCKET_TARGETS_RAW)


def _overall_severity_targets() -> OrderedDict[str, float]:
    totals = OrderedDict((severity, 0.0) for severity in ALL_SEVERITIES)
    for incident_type, type_weight in INCIDENT_TYPE_TARGETS.items():
        for severity, severity_weight in SEVERITY_TARGETS_BY_TYPE[incident_type].items():
            totals[severity] += type_weight * severity_weight
    return totals


SEVERITY_TARGETS_OVERALL: Final[OrderedDict[str, float]] = _overall_severity_targets()


def _load_payload(path: Path = SYNTHETIC_INCIDENTS_PATH) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not path.is_file():
        raise FileNotFoundError(f"Synthetic incident file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        incidents = list(payload.get("incidents", []))
        metadata = dict(payload.get("metadata", {}))
        return metadata, incidents
    if isinstance(payload, list):
        return {}, list(payload)
    raise ValueError("synthetic_incidents.json must contain a top-level object or array.")


def _percent_distribution(counts: OrderedDict[str, int], total: int) -> OrderedDict[str, float]:
    if total <= 0:
        return OrderedDict((key, 0.0) for key in counts)
    return OrderedDict((key, (value / total) * 100.0) for key, value in counts.items())


def _percentage_targets(weights: OrderedDict[str, float]) -> OrderedDict[str, float]:
    return OrderedDict((key, value * 100.0) for key, value in weights.items())


def _deviation_fraction(target_pct: float, actual_pct: float) -> float:
    if target_pct <= 0:
        return 0.0 if actual_pct <= 0 else 1.0
    return abs(actual_pct - target_pct) / target_pct


def _bucket_status(deviation_fraction: float) -> str:
    if deviation_fraction > FAIL_DEVIATION:
        return "FAIL"
    if deviation_fraction > ACCEPTABLE_DEVIATION:
        return "WARN"
    return "PASS"


def _group_status(deviations: list[float]) -> str:
    if not deviations:
        return "FAIL"
    if any(value > FAIL_DEVIATION for value in deviations):
        return "FAIL"
    if any(value > ACCEPTABLE_DEVIATION for value in deviations):
        return "WARN"
    return "PASS"


def _hour_bucket_label(hour: int) -> str:
    normalized_hour = int(hour) % 24
    if 0 <= normalized_hour <= 5:
        return "00:00-05:59"
    if 6 <= normalized_hour <= 8:
        return "06:00-08:59"
    if 9 <= normalized_hour <= 11:
        return "09:00-11:59"
    if 12 <= normalized_hour <= 14:
        return "12:00-14:59"
    if 15 <= normalized_hour <= 17:
        return "15:00-17:59"
    if 18 <= normalized_hour <= 20:
        return "18:00-20:59"
    return "21:00-23:59"


def _format_pct(value: float) -> str:
    return f"{value:.1f}%"


def _format_deviation(actual_pct: float, target_pct: float) -> str:
    signed_delta = actual_pct - target_pct
    return f"{signed_delta:+.1f}%"


def _build_distribution_table(
    title: str,
    target_weights: OrderedDict[str, float],
    actual_counts: OrderedDict[str, int],
) -> dict[str, Any]:
    total = sum(actual_counts.values())
    target_pct = _percentage_targets(target_weights)
    actual_pct = _percent_distribution(actual_counts, total)
    rows: list[dict[str, Any]] = []
    deviations: list[float] = []
    for key in target_weights.keys():
        deviation = _deviation_fraction(target_pct[key], actual_pct.get(key, 0.0))
        deviations.append(deviation)
        rows.append(
            {
                "bucket": key,
                "target_pct": round(target_pct[key], 2),
                "actual_pct": round(actual_pct.get(key, 0.0), 2),
                "delta_pct_points": round(actual_pct.get(key, 0.0) - target_pct[key], 2),
                "relative_deviation_pct": round(deviation * 100.0, 2),
                "status": _bucket_status(deviation),
            }
        )

    return {
        "title": title,
        "total": total,
        "rows": rows,
        "status": _group_status(deviations),
        "warning": any(value > ACCEPTABLE_DEVIATION for value in deviations),
    }


def _render_box_table(title: str, rows: list[dict[str, Any]]) -> str:
    headers = ["Bucket", "Target", "Actual", "Deviation"]
    display_rows = [
        [
            str(row["bucket"]),
            _format_pct(float(row["target_pct"])),
            _format_pct(float(row["actual_pct"])),
            _format_deviation(float(row["actual_pct"]), float(row["target_pct"])),
        ]
        for row in rows
    ]
    column_widths = [
        max(len(headers[index]), *(len(row[index]) for row in display_rows))
        for index in range(len(headers))
    ]

    def border(left: str, middle: str, right: str) -> str:
        return left + middle.join("─" * (width + 2) for width in column_widths) + right

    def render_row(values: list[str]) -> str:
        padded = [f" {value.ljust(column_widths[index])} " for index, value in enumerate(values)]
        return "│" + "│".join(padded) + "│"

    lines = [title, border("┌", "┬", "┐"), render_row(headers), border("├", "┼", "┤")]
    lines.extend(render_row(row) for row in display_rows)
    lines.append(border("└", "┴", "┘"))
    return "\n".join(lines)


def _render_group_status(status: str) -> str:
    if status == "PASS":
        return "Status: ✓ Within acceptable range"
    if status == "WARN":
        return "Status: ⚠ Distribution warning"
    return "Status: ✗ Major distribution breakdown"


def _severity_by_type_report(incidents: list[dict[str, Any]]) -> dict[str, Any]:
    reports: OrderedDict[str, Any] = OrderedDict()
    for incident_type, severity_targets in SEVERITY_TARGETS_BY_TYPE.items():
        counts = OrderedDict((severity, 0) for severity in severity_targets.keys())
        matching = [incident for incident in incidents if str(incident.get("type")) == incident_type]
        for incident in matching:
            severity = str(incident.get("severity"))
            if severity in counts:
                counts[severity] += 1
        reports[incident_type] = _build_distribution_table(
            f"Severity Distribution — {incident_type}",
            severity_targets,
            counts,
        )
    return reports


def _collect_counts(
    incidents: list[dict[str, Any]],
) -> tuple[OrderedDict[str, int], OrderedDict[str, int], OrderedDict[str, int], OrderedDict[str, int]]:
    type_counts = OrderedDict((key, 0) for key in INCIDENT_TYPE_TARGETS.keys())
    city_counts = OrderedDict((key, 0) for key in CITY_TARGETS.keys())
    time_counts = OrderedDict((key, 0) for key in TIME_BUCKET_TARGETS.keys())
    severity_counts = OrderedDict((key, 0) for key in ALL_SEVERITIES)

    for incident in incidents:
        incident_type = str(incident.get("type", "")).strip()
        city = str(incident.get("city", "")).strip()
        severity = str(incident.get("severity", "")).strip()
        timestamp = datetime.fromisoformat(str(incident.get("timestamp")))
        bucket = _hour_bucket_label(timestamp.hour)

        if incident_type in type_counts:
            type_counts[incident_type] += 1
        if city in city_counts:
            city_counts[city] += 1
        if bucket in time_counts:
            time_counts[bucket] += 1
        if severity in severity_counts:
            severity_counts[severity] += 1

    return type_counts, city_counts, time_counts, severity_counts


def _age_statistics(incidents: list[dict[str, Any]]) -> dict[str, Any]:
    ages = [int(incident["patient_age"]) for incident in incidents if incident.get("patient_age") is not None]
    if not ages:
        return {
            "mean": 0.0,
            "median": 0.0,
            "std": 0.0,
            "target_mean": TARGET_AGE_MEAN,
            "status": "FAIL",
        }

    mean_age = statistics.fmean(ages)
    median_age = statistics.median(ages)
    std_age = statistics.pstdev(ages) if len(ages) > 1 else 0.0
    deviation = abs(mean_age - TARGET_AGE_MEAN) / TARGET_AGE_MEAN
    return {
        "mean": round(mean_age, 2),
        "median": round(float(median_age), 2),
        "std": round(std_age, 2),
        "target_mean": TARGET_AGE_MEAN,
        "status": _bucket_status(deviation),
        "relative_deviation_pct": round(deviation * 100.0, 2),
    }


def build_validation_report(metadata: dict[str, Any], incidents: list[dict[str, Any]]) -> dict[str, Any]:
    type_counts, city_counts, time_counts, severity_counts = _collect_counts(incidents)
    incident_type_report = _build_distribution_table(
        "Incident Type Distribution",
        INCIDENT_TYPE_TARGETS,
        type_counts,
    )
    city_report = _build_distribution_table("City Distribution", CITY_TARGETS, city_counts)
    time_report = _build_distribution_table("Time-of-Day Distribution", TIME_BUCKET_TARGETS, time_counts)
    severity_report = _build_distribution_table(
        "Severity Distribution",
        SEVERITY_TARGETS_OVERALL,
        severity_counts,
    )
    severity_by_type = _severity_by_type_report(incidents)
    age_report = _age_statistics(incidents)

    statuses = [
        incident_type_report["status"],
        city_report["status"],
        time_report["status"],
        severity_report["status"],
        age_report["status"],
    ]
    overall_status = "PASS"
    if any(status == "FAIL" for status in statuses):
        overall_status = "FAIL"
    elif any(status == "WARN" for status in statuses):
        overall_status = "WARN"

    return {
        "generated_at": datetime.now(KOLKATA_TZ).isoformat(),
        "source_metadata": metadata,
        "total_incidents": len(incidents),
        "distributions": {
            "incident_type": incident_type_report,
            "city": city_report,
            "time_of_day": time_report,
            "severity": severity_report,
            "severity_by_type": severity_by_type,
        },
        "patient_age": age_report,
        "overall_status": overall_status,
    }


def render_validation_report(report: dict[str, Any]) -> str:
    source_metadata = report.get("source_metadata", {})
    seed = source_metadata.get("random_seed", "unknown")
    lines = [
        "SYNTHETIC DATA VALIDATION REPORT",
        f"Generated: {report['total_incidents']} incidents  Seed: {seed}",
        "════════════════════════════════════",
        "",
    ]

    for section_key in ["incident_type", "city", "time_of_day", "severity"]:
        section = report["distributions"][section_key]
        lines.append(_render_box_table(section["title"], section["rows"]))
        lines.append(_render_group_status(section["status"]))
        lines.append("")

    lines.append("Severity Distribution by Incident Type")
    for incident_type, section in report["distributions"]["severity_by_type"].items():
        lines.append(_render_box_table(f"  {incident_type}", section["rows"]))
        lines.append(f"  {_render_group_status(section['status'])}")
        lines.append("")

    age = report["patient_age"]
    age_status = "✓" if age["status"] == "PASS" else "⚠ WARNING" if age["status"] == "WARN" else "✗ FAIL"
    lines.extend(
        [
            "Patient Age Statistics",
            f"Mean: {age['mean']:.2f}  Median: {age['median']:.2f}  Std: {age['std']:.2f}",
            f"Target mean: ~52  Status: {age_status}",
            "",
            f"Overall validation: {report['overall_status']}",
        ]
    )
    return "\n".join(lines)


def save_report(report: dict[str, Any], path: Path = VALIDATION_REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> None:
    metadata, incidents = _load_payload()
    if not incidents:
        raise ValueError("No incidents found in synthetic_incidents.json.")

    report = build_validation_report(metadata, incidents)
    save_report(report)
    print(render_validation_report(report))


if __name__ == "__main__":
    main()
