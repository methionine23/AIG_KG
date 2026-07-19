# AIG-KG — Graph Data Model

## Design stance: patient + date are the backbone; links between events are optional

Real EMR events do **not** reliably connect. A diagnosis can arrive from an outside clinic with
no encounter and no lab; a medication may have no visit; some encounters are virtual. So the
model does **not** hang events off a visit hierarchy. Instead:

- **Every event attaches to the `Patient`** (the one always-present relationship).
- **Every event carries its own date** — the reliable key for alignment across sources.
- **Links *between* events (e.g., diagnosis→visit, lab→encounter) are optional and best-effort**,
  added only when a source key actually matches, and their coverage is measured, not assumed.

The graph still has **two layers** sharing one store:

1. **Instance layer** — the `Patient` and their dated **event** nodes (from the six tables).
2. **Ontology backbone** — standard concepts + the genetic layer (gene/disease/phenotype).

Events connect to the backbone via `OF_CONCEPT`, so patient-level analytics and knowledge-level
reasoning live in one graph.

```
                         ONTOLOGY BACKBONE
        (:Concept)──IS_A──▶(:Concept)   (:Gene)──CAUSES──▶(:Disease)
             ▲                                               │ HAS_PHENOTYPE
             │ OF_CONCEPT                                     ▼
             │                                          (:Concept HPO)
   ┌─────────┴───────────────── INSTANCE LAYER ──────────────────┐
   │                                                             │
   │   (:ConditionEvent  date)                                   │
   │   (:MeasurementEvent date,value)     each event:            │
   │   (:DrugOrderEvent   date)     ┌── HAS_EVENT ──(:Patient)    │
   │   (:VisitEvent       date,mod) │      (CURR_CLINIC)          │
   │   (:AppointmentEvent date,svc) │                            │
   │            ╎                                                 │
   │            ╎ DURING  (OPTIONAL, only if a visit key matches) │
   │            ▼                                                 │
   │   (:VisitEvent)                                              │
   └─────────────────────────────────────────────────────────────┘
```

Solid = always present. `╎` dotted = optional, coverage-measured.

---

## Node types

### Instance layer

| Label | Key | Core properties | From table |
|-------|-----|-----------------|-----------|
| `Patient` | `person_id` (= `CURR_CLINIC`) | `birth_year` | demographics |
| `ConditionEvent` | `person_id` + `event_date` + `source_code` | `event_date`, `source_code`, `source_vocab` (ICD10CM/ICD9CM/HIC), `source_name`, `is_primary`, `visit_id?` | diagnosis |
| `VisitEvent` | `visit_id` (`Visit_Nbr`) | `event_date` (arrive), `end_date?`, `visit_type` (inpatient/ED/outpatient), `modality` (in-person/virtual) | encounter |
| `AppointmentEvent` | `person_id` + `event_date` + `specialty` | `event_date`, `specialty` (`Appt_Clinical_Service`), `appt_type`, `modality` | appointment |
| `DrugOrderEvent` | `person_id` + `event_date` + `source_code` | `event_date`, `source_code` (local→RxNorm later), `source_name` | medication (orders, drug-filtered) |
| `MeasurementEvent` | `person_id` + `event_date` + `source_code` | `event_date`, `value_as_number`, `value_as_string`, `unit`, `source_code` (local→LOINC later), `source_name` | lab |

Every event node also carries `source_table` (provenance) so we always know which single source
it came from — supporting principle 2 (treat each table as its own source; verify cross-links
later).

### Ontology backbone

| Label | Key | Core properties | From |
|-------|-----|-----------------|------|
| `Concept` | `concept_id` (OMOP) | `curie`, `name`, `vocab`, `domain`, `standard` | OHDSI Athena; local codes get a `local:` concept until crosswalked |
| `Gene` | `symbol` | `symbol`, `ensembl` | HGNC / PrimeKG |
| `Disease` | `curie` (`MONDO:`/`OMIM:`) | `name`, `inheritance` | MONDO/OMIM / PrimeKG |

---

## Relationship (edge) types

| Edge | From → To | Always present? | Meaning |
|------|-----------|-----------------|---------|
| `HAS_EVENT` | Patient → *any Event* | **Yes** | the patient experienced this dated event — the reliable backbone link |
| `OF_CONCEPT` | Event → Concept | when code maps | anchors the event to standardized meaning (or a `local:` concept) |
| `DURING` | Condition/Drug/Measurement → VisitEvent | **Optional** | event occurred within a visit — added **only** when a source visit key matches; coverage measured |
| `IS_A` | Concept → Concept | backbone | vocabulary hierarchy (SNOMED/LOINC/RxNorm/ICD subsumption) |
| `MAPS_TO` | Concept → Concept | backbone | crosswalk: source→standard, local→LOINC/RxNorm, HPO↔SNOMED |
| `CAUSES` | Gene → Disease | backbone | causal gene–disease (genetic layer) |
| `HAS_PHENOTYPE` | Disease → Concept(HPO) | backbone | disease phenotype |
| `NEXT` | Event → Event (same patient) | **Optional/derived** | consecutive-in-time ordering; a convenience materialized from dates (see timing) |

**Why `HAS_EVENT` and not `HAS_VISIT` as the hub:** a transferred outside diagnosis with no
encounter, a med with no visit, or a lone lab all still attach cleanly to the patient and sit on
the timeline. Nothing depends on a visit existing.

---

## Capturing timing

Time is the load-bearing dimension, and per your point 3 the **date is the alignment key**.
Three complementary mechanisms, in order of importance:

### 1. Dates as event attributes (primary, always present)
Each event stores `event_date` (and `end_date`/`event_time` where available). A patient's
**timeline is simply their set of events ordered by `event_date`** — computed by reading
attributes, never by traversing visit structure. This is robust to missing visits/tests and to
mixed sources. Every use case reads from here:
- **U1 diagnostic delay** = `event_date`(anchor: dx / genetic test / therapy) − `event_date`(first red-flag feature). Pure date arithmetic over the patient's events; no visit needed.
- **U2 density** = counts and inter-event gaps over `event_date`, sliceable by event type and by `modality` (virtual vs in-person — virtual visits are easier to schedule, so burden must distinguish them).
- **U3 control trajectory** = `MeasurementEvent.value_as_number` ordered by `event_date` for a lab concept set (e.g., HbA1c).

### 2. Relative-time alignment (anchoring t = 0)
To compare patients, we re-express absolute dates as **time relative to a reference event** —
e.g., `t = 0` at the ATTR diagnosis anchor, or at the first red-flag feature. Alignment is a
per-patient offset applied to `event_date`; it needs only dates, so it survives missing links.
This is how "years from first feature to diagnosis" is made comparable across the cohort.

### 3. Ordering edges `NEXT` (optional, derived, for traversal & viz)
For path-style queries and trajectory visualization we can **materialize** `NEXT` edges between
a patient's consecutive events (globally, or within a domain such as visit→visit). These are a
convenience **derived from the dates** and fully recomputable — the attributes in (1) remain the
source of truth. We add them where they help; we never depend on them for correctness.

> Optional enrichment (later): calendar/time-bin nodes (e.g., a node per year-quarter) that
> events link to, for cross-patient alignment by calendar or cohort-level density heatmaps. Not
> needed for the prototype; the attribute + relative-time approach covers U1–U3.

### Missing / unmatched links are first-class
- No visit for a diagnosis, no encounter for a lab, no test for a med → the event still exists,
  dated, on the patient timeline. `DURING` is simply absent.
- `DURING` and any other cross-table join (principle 2) is added only on a real key match, and
  its **coverage is reported as a data-quality metric** (e.g., "% of diagnoses with a matching
  encounter", "% virtual visits") — never assumed to be 100%.

---

## How the two layers serve reasoning

Because events anchor to the backbone via `OF_CONCEPT`, one traversal goes from a gene, through
disease phenotypes, to the standardized conditions actually observed on a patient's timeline —
e.g., *"patients with `TTR` `CAUSES` ATTR whose earliest event in the ATTR red-flag concept set
precedes their ATTR diagnosis date by > N months"* — computed from event **dates**, independent
of whether those events shared a visit. This is the structural basis for the MVP in
[`MVP_TTR.md`](MVP_TTR.md).

## Concept sets

Analytic definitions (red-flag features, diagnosis codes, drug classes, lab panels) are
**versioned concept sets** — lists of `concept_id`s (standard, or `local:` codes for uncrosswalked
lab/med codes), optionally expanded down `IS_A`. They live in code/config, are
clinician-reviewable, and are the unit we validate.
