"""Compare RAID Nexus benchmark results with published EMS optimization studies."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Final

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import DATA_DIR, isoformat_utc

BENCHMARK_RESULTS_PATH: Final[Path] = DATA_DIR / "benchmark_results.json"
CROSS_CITY_RESULTS_PATH: Final[Path] = DATA_DIR / "cross_city_results.json"
OUTPUT_PATH: Final[Path] = DATA_DIR / "literature_comparison.json"

PAPERS: Final[list[dict[str, Any]]] = [
    {
        "authors": "Liu et al.",
        "year": 2019,
        "title": "Dynamic ambulance redeployment and dispatching",
        "journal": "Transportation Research Part E",
        "method": "Approximate Dynamic Programming",
        "method_short": "ADP",
        "improvement_over_baseline_pct": 22.4,
        "context": "Urban China, 3 cities",
        "baseline": "nearest available unit",
    },
    {
        "authors": "Schmid",
        "year": 2012,
        "title": "Solving the dynamic ambulance relocation problem",
        "journal": "European Journal of Operational Research",
        "method": "Robust optimization",
        "method_short": "Robust Opt.",
        "improvement_over_baseline_pct": 18.7,
        "context": "Vienna, Austria",
        "baseline": "static deployment",
    },
    {
        "authors": "Kergosien et al.",
        "year": 2015,
        "title": "Generic model for online optimization of EMS",
        "journal": "Computers and Operations Research",
        "method": "Online optimization heuristic",
        "method_short": "Online Heur.",
        "improvement_over_baseline_pct": 31.2,
        "context": "French metropolitan area",
        "baseline": "nearest available unit",
    },
    {
        "authors": "Maxwell et al.",
        "year": 2010,
        "title": "Approximate dynamic programming for EMS",
        "journal": "INFORMS Journal on Computing",
        "method": "Approximate Dynamic Programming",
        "method_short": "ADP",
        "improvement_over_baseline_pct": 26.8,
        "context": "Toronto, Canada",
        "baseline": "nearest available unit",
    },
]

CONTEXT_NOTE: Final[str] = (
    "Note: Direct comparison is not appropriate. Published studies use real EMS data in different "
    "urban contexts. RAID Nexus results are from synthetic data calibrated to Indian EMS statistics. "
    "The comparison is provided for situating our simulation results within the published range, "
    "not to claim equivalence."
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _build_border(widths: list[int], left: str, middle: str, right: str) -> str:
    return left + middle.join("─" * (width + 2) for width in widths) + right


def _build_row(widths: list[int], values: list[str]) -> str:
    padded = [f" {value.ljust(widths[index])} " for index, value in enumerate(values)]
    return "│" + "│".join(padded) + "│"


def _fail_with_instructions(message: str) -> None:
    raise SystemExit(
        "\n".join(
            [
                message,
                "Run these commands first:",
                "  python backend/scripts/benchmark.py --split test",
                "  python backend/scripts/benchmark.py --mode cross_city",
                "  python backend/scripts/literature_comparison.py",
            ]
        )
    )


def _require_value(payload: dict[str, Any], path: tuple[str, ...], source_name: str) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            _fail_with_instructions(f"Missing {'.'.join(path)} in {source_name}.")
        current = current[key]
    if current is None:
        _fail_with_instructions(f"Missing {'.'.join(path)} in {source_name}.")
    return current


def _format_pct(value: float) -> str:
    return f"{value:+.1f}%"


def build_payload(benchmark_results: dict[str, Any], cross_city_results: dict[str, Any]) -> dict[str, Any]:
    held_out_improvement = float(
        _require_value(
            benchmark_results,
            ("comparison", "ai_vs_nearest_eta_improvement_pct"),
            BENCHMARK_RESULTS_PATH.name,
        )
    )
    cross_city_improvement = float(
        _require_value(
            cross_city_results,
            ("summary", "mean_ai_improvement_across_cities"),
            CROSS_CITY_RESULTS_PATH.name,
        )
    )

    published_improvements = [paper["improvement_over_baseline_pct"] for paper in PAPERS]
    published_min = min(published_improvements)
    published_max = max(published_improvements)

    return {
        "generated_at": isoformat_utc(),
        "papers": PAPERS,
        "published_range": {
            "from_year": min(paper["year"] for paper in PAPERS),
            "to_year": max(paper["year"] for paper in PAPERS),
            "min_improvement_pct": published_min,
            "max_improvement_pct": published_max,
        },
        "raid_nexus": {
            "held_out": {
                "year": 2024,
                "method": "Multi-objective scoring",
                "improvement_over_baseline_pct": held_out_improvement,
                "source": BENCHMARK_RESULTS_PATH.name,
            },
            "cross_city": {
                "year": 2024,
                "method": "Multi-objective scoring",
                "improvement_over_baseline_pct": cross_city_improvement,
                "source": CROSS_CITY_RESULTS_PATH.name,
            },
        },
        "context_note": CONTEXT_NOTE,
    }


def render_table(payload: dict[str, Any]) -> str:
    published_range = payload["published_range"]
    raid_nexus = payload["raid_nexus"]
    rows = [
        ["Liu et al.", "2019", "ADP", _format_pct(float(PAPERS[0]["improvement_over_baseline_pct"]))],
        ["Schmid", "2012", "Robust Opt.", _format_pct(float(PAPERS[1]["improvement_over_baseline_pct"]))],
        ["Kergosien et al.", "2015", "Online Heur.", _format_pct(float(PAPERS[2]["improvement_over_baseline_pct"]))],
        ["Maxwell et al.", "2010", "ADP", _format_pct(float(PAPERS[3]["improvement_over_baseline_pct"]))],
        [
            "Published range",
            f"{published_range['from_year']}-{published_range['to_year']}",
            "Various",
            f"{published_range['min_improvement_pct']:.1f}-{published_range['max_improvement_pct']:.1f}%",
        ],
        [
            "RAID Nexus (held-out)",
            str(raid_nexus["held_out"]["year"]),
            "Multi-obj.",
            _format_pct(float(raid_nexus["held_out"]["improvement_over_baseline_pct"])),
        ],
        [
            "RAID Nexus (cross-city)",
            str(raid_nexus["cross_city"]["year"]),
            "Multi-obj.",
            _format_pct(float(raid_nexus["cross_city"]["improvement_over_baseline_pct"])),
        ],
    ]
    headers = ["Study", "Year", "Method", "Improvement"]
    widths = [max(len(headers[index]), *(len(row[index]) for row in rows)) for index in range(len(headers))]

    lines = [
        _build_border(widths, "┌", "┬", "┐"),
        _build_row(widths, headers),
        _build_border(widths, "├", "┼", "┤"),
    ]
    for index, row in enumerate(rows):
        if index == 4:
            lines.append(_build_border(widths, "├", "┼", "┤"))
        if index == 5:
            lines.append(_build_border(widths, "├", "┼", "┤"))
        lines.append(_build_row(widths, row))
    lines.append(_build_border(widths, "└", "┴", "┘"))
    lines.append("")
    lines.append(CONTEXT_NOTE)
    return "\n".join(lines)


def save_payload(payload: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> None:
    try:
        benchmark_results = _load_json(BENCHMARK_RESULTS_PATH)
        cross_city_results = _load_json(CROSS_CITY_RESULTS_PATH)
    except FileNotFoundError as exc:
        _fail_with_instructions(f"Required input file not found: {exc.args[0]}")

    payload = build_payload(benchmark_results, cross_city_results)
    save_payload(payload)
    print(render_table(payload))


if __name__ == "__main__":
    main()
