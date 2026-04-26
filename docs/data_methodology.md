# Synthetic Data Methodology — RAID Nexus

## 1. Purpose

RAID Nexus uses synthetic incident data because real emergency medical services call records were not available to the project team in a de-identified, research-usable format. The synthetic dataset is used for benchmarking dispatch strategies, evaluating fairness metrics, stress-testing the command center, and validating system behaviour under repeatable operating conditions. It is not used as training data for a learned dispatch model. The key methodological limitation is that benchmark results are valid only within the calibrated synthetic distribution represented by the generator configuration and recorded output metadata.

## 2. Generation Parameters

| Parameter | Value | Source | Notes |
|---|---|---|---|
| Incident type distribution | `cardiac 20%`, `trauma 18%`, `accident 22%`, `respiratory 15%`, `stroke 15%`, `other 10%` | WHO Global Health Estimates 2023; Garg et al. (2019), *Indian Journal of Critical Care Medicine*; MoRTH Road Accidents in India 2022; Salvi et al. (2018), *Lancet Global Health*; Pandian et al. (2018), *Neuroepidemiology* | Weekend generation applies calibrated multipliers before sampling, so observed type mix reflects weekday/weekend blending rather than a perfectly static ratio. |
| Severity distribution by incident type | `cardiac: critical 0.40, high 0.35, medium 0.25`<br>`trauma: critical 0.30, high 0.40, medium 0.30`<br>`accident: critical 0.20, high 0.45, medium 0.35`<br>`respiratory: high 0.30, medium 0.50, low 0.20`<br>`stroke: critical 0.50, high 0.40, medium 0.10`<br>`other: medium 0.60, low 0.40` | Calibrated from the same emergency presentation sources used for incident-type weighting | These are conditional severity priors applied after incident type selection. |
| Time-of-day weights | `00:00-05:59 0.05`, `06:00-08:59 0.08`, `09:00-11:59 0.14`, `12:00-14:59 0.11`, `15:00-17:59 0.12`, `18:00-20:59 0.18`, `21:00-23:59 0.10` | Mahajan et al. (2021), *Emergency Medicine Journal* | These are relative sampling weights normalized internally by `random.choices()`. Peak demand is intentionally concentrated in the 18:00-20:59 window. |
| Weekend variation | `accident ×1.3`, `trauma ×1.2`, `cardiac ×0.9`, others unchanged | Derived from the temporal-risk assumption added in generator version `1.1` | Applied only on Saturday/Sunday after timestamp selection to reflect higher weekend trauma and accident incidence. |
| City population weights | `Delhi 22%`, `Mumbai 22%`, `Bengaluru 18%`, `Chennai 18%`, `Hyderabad 20%` | Census of India 2011 (projected); Karnataka State Planning Board 2023; Tamil Nadu Economic Appraisal 2023; Telangana State Development Planning Society 2023 | City counts are allocated deterministically from these weights for reproducible benchmark batches. |
| Patient age distribution | `18-30 10%`, `31-44 18%`, `45-60 37%`, `61-70 23%`, `71-85 12%` | Farooqui et al. (2019), *Journal of Emergencies, Trauma and Shock* | The distribution is weighted toward ages 45-70 to align with the cited mean emergency-patient age of about 52 years. |
| Geographic sampling | Uniform random latitude/longitude within fixed city bounding boxes | Internal simulation design | This is a known simplification and is treated as a limitation rather than a realistic spatial process. |

## 3. Reproducibility

All synthetic incident generation uses random seed `42` by default, and the exact seed used for a given dataset is recorded in the top-level `metadata.random_seed` field of `backend/data/synthetic_incidents.json`. Generator version metadata is also written into the same output object so downstream benchmark and validation runs can be traced to a specific generator configuration.

The exact command used to regenerate the canonical dataset is:

```bash
python backend/scripts/generate_incidents.py --count 500 --seed 42
```

The generated output has the following envelope:

```json
{
  "metadata": {
    "generated_at": "ISO8601 timestamp",
    "random_seed": 42,
    "generator_version": "1.1",
    "total_incidents": 500,
    "calibration_sources": [
      "WHO Global Health Estimates 2023",
      "MoRTH Road Accidents in India 2022",
      "Census of India 2011 (projected)",
      "Mahajan et al. (2021) Emergency Medicine Journal",
      "Farooqui et al. (2019) JETS"
    ]
  },
  "incidents": []
}
```

## 4. Validation

The script `backend/scripts/validate_synthetic_data.py` loads the generated dataset, computes realized distributions, compares them to the calibrated targets, and writes a structured JSON report to `backend/data/validation_report.json`. Each bucket is evaluated using a relative deviation test: `|actual% - target%| / target%`. A deviation above `5%` is flagged as a distribution warning. `PASS` means no warnings were detected, `WARN` indicates drift outside the acceptance threshold without structural failure, and `FAIL` is reserved for load/shape errors or major breakdowns.

Sample output from an actual run on `500` incidents with seed `42`:

```text
SYNTHETIC DATA VALIDATION REPORT
Generated: 500 incidents  Seed: 42
════════════════════════════════════

Incident Type Distribution
┌─────────────┬────────┬────────┬───────────┐
│ Bucket      │ Target │ Actual │ Deviation │
├─────────────┼────────┼────────┼───────────┤
│ cardiac     │ 19.0%  │ 19.8%  │ +0.8%     │
│ trauma      │ 18.6%  │ 16.8%  │ -1.8%     │
│ accident    │ 23.3%  │ 20.8%  │ -2.5%     │
│ respiratory │ 14.7%  │ 15.6%  │ +0.9%     │
│ stroke      │ 14.7%  │ 16.0%  │ +1.3%     │
│ other       │ 9.8%   │ 11.0%  │ +1.2%     │
└─────────────┴────────┴────────┴───────────┘
Status: ⚠ Distribution warning

City Distribution
┌───────────┬────────┬────────┬───────────┐
│ Bucket    │ Target │ Actual │ Deviation │
├───────────┼────────┼────────┼───────────┤
│ Delhi     │ 22.0%  │ 22.0%  │ +0.0%     │
│ Mumbai    │ 22.0%  │ 22.0%  │ +0.0%     │
│ Bengaluru │ 18.0%  │ 18.0%  │ +0.0%     │
│ Chennai   │ 18.0%  │ 18.0%  │ +0.0%     │
│ Hyderabad │ 20.0%  │ 20.0%  │ +0.0%     │
└───────────┴────────┴────────┴───────────┘
Status: ✓ Within acceptable range

Time-of-Day Distribution
┌─────────────┬────────┬────────┬───────────┐
│ Bucket      │ Target │ Actual │ Deviation │
├─────────────┼────────┼────────┼───────────┤
│ 00:00-05:59 │ 6.4%   │ 6.4%   │ -0.0%     │
│ 06:00-08:59 │ 10.3%  │ 12.4%  │ +2.1%     │
│ 09:00-11:59 │ 17.9%  │ 17.6%  │ -0.3%     │
│ 12:00-14:59 │ 14.1%  │ 13.4%  │ -0.7%     │
│ 15:00-17:59 │ 15.4%  │ 16.4%  │ +1.0%     │
│ 18:00-20:59 │ 23.1%  │ 22.0%  │ -1.1%     │
│ 21:00-23:59 │ 12.8%  │ 11.8%  │ -1.0%     │
└─────────────┴────────┴────────┴───────────┘
Status: ⚠ Distribution warning

Severity Distribution
┌──────────┬────────┬────────┬───────────┐
│ Bucket   │ Target │ Actual │ Deviation │
├──────────┼────────┼────────┼───────────┤
│ critical │ 25.2%  │ 25.2%  │ +0.0%     │
│ high     │ 34.8%  │ 34.6%  │ -0.2%     │
│ medium   │ 33.1%  │ 33.0%  │ -0.1%     │
│ low      │ 6.8%   │ 7.2%   │ +0.4%     │
└──────────┴────────┴────────┴───────────┘
Status: ⚠ Distribution warning

Severity Distribution by Incident Type
  cardiac
┌──────────┬────────┬────────┬───────────┐
│ Bucket   │ Target │ Actual │ Deviation │
├──────────┼────────┼────────┼───────────┤
│ critical │ 40.0%  │ 44.4%  │ +4.4%     │
│ high     │ 35.0%  │ 34.3%  │ -0.7%     │
│ medium   │ 25.0%  │ 21.2%  │ -3.8%     │
└──────────┴────────┴────────┴───────────┘
  Status: ⚠ Distribution warning

  trauma
┌──────────┬────────┬────────┬───────────┐
│ Bucket   │ Target │ Actual │ Deviation │
├──────────┼────────┼────────┼───────────┤
│ critical │ 30.0%  │ 27.4%  │ -2.6%     │
│ high     │ 40.0%  │ 40.5%  │ +0.5%     │
│ medium   │ 30.0%  │ 32.1%  │ +2.1%     │
└──────────┴────────┴────────┴───────────┘
  Status: ⚠ Distribution warning

  accident
┌──────────┬────────┬────────┬───────────┐
│ Bucket   │ Target │ Actual │ Deviation │
├──────────┼────────┼────────┼───────────┤
│ critical │ 20.0%  │ 18.3%  │ -1.7%     │
│ high     │ 45.0%  │ 49.0%  │ +4.0%     │
│ medium   │ 35.0%  │ 32.7%  │ -2.3%     │
└──────────┴────────┴────────┴───────────┘
  Status: ⚠ Distribution warning

  respiratory
┌────────┬────────┬────────┬───────────┐
│ Bucket │ Target │ Actual │ Deviation │
├────────┼────────┼────────┼───────────┤
│ high   │ 30.0%  │ 24.4%  │ -5.6%     │
│ medium │ 50.0%  │ 56.4%  │ +6.4%     │
│ low    │ 20.0%  │ 19.2%  │ -0.8%     │
└────────┴────────┴────────┴───────────┘
  Status: ⚠ Distribution warning

  stroke
┌──────────┬────────┬────────┬───────────┐
│ Bucket   │ Target │ Actual │ Deviation │
├──────────┼────────┼────────┼───────────┤
│ critical │ 50.0%  │ 50.0%  │ +0.0%     │
│ high     │ 40.0%  │ 43.8%  │ +3.8%     │
│ medium   │ 10.0%  │ 6.2%   │ -3.8%     │
└──────────┴────────┴────────┴───────────┘
  Status: ✗ Major distribution breakdown

  other
┌────────┬────────┬────────┬───────────┐
│ Bucket │ Target │ Actual │ Deviation │
├────────┼────────┼────────┼───────────┤
│ medium │ 60.0%  │ 61.8%  │ +1.8%     │
│ low    │ 40.0%  │ 38.2%  │ -1.8%     │
└────────┴────────┴────────┴───────────┘
  Status: ✓ Within acceptable range

Patient Age Statistics
Mean: 52.46  Median: 54.00  Std: 15.11
Target mean: ~52  Status: ✓

Overall validation: WARN
```

## 5. Limitations

1. Incident locations are uniformly distributed within city bounding
   boxes. Real incidents cluster near residential areas, highways, and
   commercial zones — patterns not captured by uniform sampling.

2. Severity distributions are estimated from emergency department
   presentations, not pre-hospital triage data, which may differ.

3. All sources are population-level statistics. Individual city
   variations may differ significantly.

4. Temporal patterns assume consistent behaviour across weekdays
   and weekends. Real data shows weekend spikes for trauma/accident.

5. Hindi complaints are handled via offline neural translation
   (Helsinki-NLP Opus-MT) plus a small Hinglish emergency glossary.
   Translation quality for emergency medical domain text is not
   validated. All translated triage results are escalated to human
   review as a safety measure. Other non-English complaints are
   detected and escalated to human review without automatic translation.

## 6. Generalization Warning

> **Important**: Benchmark results (average ETA, specialty match rate,
> fairness metrics) reflect performance on this synthetic distribution.
> These results should not be interpreted as predictions of real-world
> performance without validation on de-identified EMS data.

## 7. Future Data Work

1. Partnership with state EMS operators for de-identified historical call data, with initial outreach targets including CATS Delhi, Kerala 108, and Karnataka 108.
2. Calibration refinement using city-level EMS annual reports so incident mix, severity balance, and temporal effects can be tuned against local operational evidence rather than national or tertiary-care aggregates.
3. Temporal pattern validation against open-source emergency call datasets such as Seattle Real Time Fire 911 Calls, not as a geographic substitute for Indian data but as a methodological reference for validating diurnal and weekday/weekend pattern analysis.
