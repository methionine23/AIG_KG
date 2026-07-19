# AIG-KG — EMR Input Spec, Cleanup & Testing Guide

How to turn your multiple raw EMR tables into the small, clean, PHI-free input the KG builder
expects — and how to build test data for it. This is the practical companion to
[`PROTOTYPE.md`](PROTOTYPE.md).

**Core idea:** don't hand-pick columns ad hoc per table. Select each source table's essential
columns **into one target schema (the "event contract")**. Every table becomes the same shape;
cleanup becomes a fixed checklist; tests become "known input → known output."

---

## 1. The target: one unified event contract

Every raw row from any table maps to **one event row** with these columns. Domain-specific
fields are simply null where they don't apply.

| Column | Type | Applies to | Meaning |
|--------|------|-----------|---------|
| `person_id` | str | all | Stable **de-identified** patient/sample ID, **identical across all tables** |
| `domain` | enum | all | `condition` \| `visit` \| `drug` \| `measurement` |
| `event_date` | date | all | The one clinically meaningful date for the event (see §3.2) |
| `end_date` | date? | visit, drug | Discharge / therapy end, if available |
| `source_code` | str | all | Code exactly as it appears in the source |
| `source_vocab` | str | all | Its code system: `ICD10CM`, `ICD9CM`, `SNOMED`, `NDC`, `RxNorm`, `LOINC`, `local`, … |
| `source_name` | str | all | Human-readable name/description |
| `value_as_number` | float? | measurement (, drug dose) | Numeric lab result / dose |
| `unit` | str? | measurement, drug | Unit for the value |
| `value_as_string` | str? | measurement, drug | Non-numeric result ("positive", "<0.1") or med route/frequency (the "quality") |
| `quantity` | float? | drug | Dispensed/ordered quantity |
| `visit_id` | str? | condition, drug, measurement | Link back to the encounter row (enables `DURING` edges) |
| `visit_type` | str? | visit | `inpatient` \| `outpatient` \| `ED` \| `telehealth` |

The `ingest` package produces exactly this DataFrame; `vocab` then adds `concept_id`/`curie`;
`graph.build_kg()` consumes it. Same contract whether the source is your EMR download or (after
OMOP mapping) All of Us.

---

## 2. Essential columns to select from each table

For each source table, keep **only** the columns below (map source name → target). Everything
else is dropped early. If a listed field doesn't exist in your data, leave the target null.

### Diagnosis table → `domain = condition`
| Keep (source) | → target | Notes |
|---|---|---|
| patient/sample id | `person_id` | must match other tables |
| diagnosis date (service/onset/recorded) | `event_date` | pick one policy, §3.2 |
| diagnosis code | `source_code` | |
| code system (ICD-10-CM / ICD-9-CM / SNOMED) | `source_vocab` | if only one system, hard-code it |
| diagnosis description | `source_name` | |
| encounter id | `visit_id` | if present |

Drop: billing modifiers, provider NPI, DRG, free-text notes, diagnosis rank/POA (unless a use
case needs them).

### Encounter table → `domain = visit`
| Keep (source) | → target | Notes |
|---|---|---|
| patient id | `person_id` | |
| encounter id | `visit_id` | the join key for other tables |
| admit/start date | `event_date` | |
| discharge/end date | `end_date` | |
| encounter type/class | `visit_type` | normalize to inpatient/outpatient/ED/telehealth |

Drop: insurance, room/bed, facility, cost, provider (unless used).

### Medication table → `domain = drug`
| Keep (source) | → target | Notes |
|---|---|---|
| patient id | `person_id` | |
| med start (order/fill/admin) date | `event_date` | **decide which med event** you track; be consistent |
| med end date | `end_date` | if available |
| drug name | `source_name` | |
| drug code (NDC / RxNorm / local) | `source_code` | |
| code system | `source_vocab` | |
| dose/strength | `value_as_number` + `unit` | e.g., 25 + "mg" |
| route / frequency (the "quality") | `value_as_string` | e.g., "PO daily" |
| quantity | `quantity` | numeric |
| encounter id | `visit_id` | if present |

Drop: prescriber, pharmacy, cost, refills (unless used).

### Lab table → `domain = measurement`
| Keep (source) | → target | Notes |
|---|---|---|
| patient id | `person_id` | |
| result/collection date | `event_date` | |
| test name | `source_name` | |
| test code (LOINC / local) | `source_code` | |
| code system | `source_vocab` | |
| numeric result | `value_as_number` | coerce to float |
| unit | `unit` | harmonize key analytes, §3.5 |
| non-numeric result ("positive", "<0.1") | `value_as_string` | keep when `value_as_number` is null |
| encounter id | `visit_id` | if present |

Drop: specimen id, analyzer, performing lab, reference range/flag (optional — keep only if a
tool uses them).

---

## 3. Cleanup checklist (run in this order)

1. **Unify `person_id`.** Same dtype (string) across all tables; strip whitespace; consistent
   casing. Confirm it is de-identified — no MRN/name/DOB leaking in.
2. **Normalize dates.** Parse to `datetime`; **choose one date per event type and document it**
   (diagnosis: date of service vs recorded; lab: collection vs result; med: order vs fill vs
   admin). Drop/flag rows with missing or implausible dates (year < 1900 or in the future).
3. **Deduplicate.** Drop exact duplicate rows; collapse same `person_id + event_date +
   source_code` duplicates (common with feeds that re-post records).
4. **Standardize codes.** Record `source_vocab` explicitly per table; uppercase codes; pick one
   ICD-10 format (with or without the dot) and apply it everywhere.
5. **Fix lab values.** Coerce `value_as_number` to float; split value from unit if combined in
   one cell; route non-numeric results to `value_as_string`; **harmonize units for the analytes
   you analyze** (e.g., glucose mg/dL vs mmol/L; HbA1c % vs mmol/mol); flag impossible values.
6. **Standardize nulls.** Convert `""`, `"NULL"`, `"NA"`, sentinel `9999`/`-1` to real `NaN`.
7. **Meds: one event definition.** Decide fill vs order vs administration and keep only that;
   parse dose/strength into number + unit.
8. **Restrict columns.** Select only the contract columns; discard the rest before anything else
   downstream sees the data.
9. **Cohort filter (optional).** Keep patients in scope, or keep all and filter in analysis.
10. **Validate.** Print per-table: row count, distinct `person_id`, `event_date` min/max, and %
    of `person_id`s present in the encounter table. Cheap checks that catch join/date bugs.

Each step becomes a small, testable function in `aig_kg.ingest`.

---

## 4. Testing strategy — your instinct, formalized

Your plan (build a DataFrame yourself, select related columns) is right. Make it robust:

- **Two layers of test data:**
  1. **Hand-built fixtures** — a few rows per table that mimic **your real column layout and its
     quirks** (mixed units, weird nulls, duplicate rows, an ICD dot inconsistency), but with
     **fabricated IDs and dates**. These test that `ingest`+cleanup handle *your* messiness.
     Live in `tests/fixtures/` and are **committed** (they're synthetic, so PHI-safe).
  2. **Synthetic generator** — `aig_kg.synth` produces a larger OMOP dataset with a planted
     ATTR signal, for volume and end-to-end/tool tests (see `PROTOTYPE.md` §6).
- **PHI rule:** never commit real rows. If you derive a fixture from a real record, fully
  fabricate the `person_id` and jitter the dates — treat it as a template, not data.
- **Test shape:** raw fixture CSV → `ingest.load_*()` → assert the resulting contract DataFrame
  equals a small expected table (types, dedup, dates, units). Known input → known output.

Example fixtures illustrating *raw* (messy) → *contract* are in
[`tests/fixtures/`](../tests/fixtures/): `diagnosis_sample.csv`, `encounter_sample.csv`,
`med_sample.csv`, `lab_sample.csv`.

---

## 5. Worked example — selecting into the contract

```python
import pandas as pd

# raw diagnosis table (your columns will differ — adjust the mapping)
raw = pd.read_csv("tests/fixtures/diagnosis_sample.csv")

dx = (
    raw.rename(columns={
        "PatientID":   "person_id",
        "DxDate":      "event_date",
        "ICD10":       "source_code",
        "DxName":      "source_name",
        "EncounterID": "visit_id",
    })
    .assign(
        domain="condition",
        source_vocab="ICD10CM",
        person_id=lambda d: d.person_id.astype(str).str.strip(),
        event_date=lambda d: pd.to_datetime(d.event_date, errors="coerce"),
        source_code=lambda d: d.source_code.str.upper().str.replace(".", "", regex=False),
    )
    .loc[:, ["person_id", "domain", "event_date", "source_code",
             "source_vocab", "source_name", "visit_id"]]
    .dropna(subset=["person_id", "event_date", "source_code"])
    .drop_duplicates(["person_id", "event_date", "source_code"])
)
```

The same pattern (rename → assign/clean → select → drop bad rows → dedupe) applies to each
table; only the column map and the domain-specific fields change. Once all four are in the
contract, `pd.concat([...])` gives the single long-event table the pipeline consumes.

---

## 6. What I need from you to tailor `ingest`

Just a **header row (column names only, no data)** from each of your four tables. With that I
map your real columns into the contract above and write the `ingest.load_*()` functions and
their fixture tests to match — no PHI required.
