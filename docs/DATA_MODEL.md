# AIG-KG — Graph Data Model

The graph has **two layers** that share the same store:

1. **Instance layer** — real patients and their dated events (from EMR extracts, staged as OMOP).
2. **Ontology backbone** — standard concepts and the biomedical relations among them
   (OMOP standard concepts + SNOMED/LOINC/RxNorm hierarchies + the genetic layer: gene/disease/phenotype).

Instance events attach to the backbone through a single relationship type (`OF_CONCEPT`), so
every patient event is anchored to standardized meaning, and knowledge-level reasoning
(gene → phenotype → observed diagnosis) and patient-level analytics happen in one graph.

```
  INSTANCE LAYER                             ONTOLOGY BACKBONE
  ─────────────                              ─────────────────
  (:Patient)                                 (:Concept {vocab:'SNOMED'})
     │ HAS_VISIT                                  ▲   ▲
     ▼                                            │IS_A│
  (:Visit)──NEXT_VISIT──▶(:Visit)                 │   │
     │ DURING                                 (:Concept)  (:Concept)
     ▼                                            ▲
  (:ConditionOccurrence)───OF_CONCEPT────────────┘
  (:DrugExposure)─────────OF_CONCEPT──▶(:Concept {vocab:'RxNorm'})
  (:Measurement)──────────OF_CONCEPT──▶(:Concept {vocab:'LOINC'})

  GENETIC LAYER (backbone)
  (:Gene {symbol:'TTR'})─CAUSES▶(:Disease {curie:'MONDO:...'})
  (:Disease)─HAS_PHENOTYPE▶(:Concept {vocab:'HPO'})
  (:Concept HPO)─MAPS_TO▶(:Concept SNOMED)   // phenotype ↔ observable dx
```

## Node types

### Instance layer

| Label | Key | Core properties | From |
|-------|-----|-----------------|------|
| `Patient` | `person_id` | `birth_year`, `sex_concept_id`, ancestry (optional) | OMOP `person` |
| `Visit` | `visit_occurrence_id` | `start_date`, `end_date`, `visit_concept_id` (in/out/ED), `care_site` | OMOP `visit_occurrence` |
| `ConditionOccurrence` | `condition_occurrence_id` | `condition_date`, `source_code`, `source_vocab` | dx extract → OMOP `condition_occurrence` |
| `DrugExposure` | `drug_exposure_id` | `start_date`, `end_date`, `quantity`, `dose`/`quality`, `source_code` | med extract → OMOP `drug_exposure` |
| `Measurement` | `measurement_id` | `date`, `value_as_number`, `unit`, `range_low/high`, `source_code` | lab extract → OMOP `measurement` |
| `Observation` | `observation_id` | `date`, `value`, `source_code` | survey / other (later) |

> Encounters in the raw "encounter" extract map to `Visit`; the "diagnosis", "med", and "lab"
> extracts map to `ConditionOccurrence`, `DrugExposure`, and `Measurement` respectively.

### Ontology backbone

| Label | Key | Core properties | From |
|-------|-----|-----------------|------|
| `Concept` | `concept_id` (OMOP) | `curie` (e.g. `SNOMED:1234`), `name`, `vocab`, `domain`, `standard` | OHDSI Athena `concept` |
| `Gene` | `hgnc` / `symbol` | `symbol`, `ensembl` | HGNC / PrimeKG |
| `Disease` | `curie` (`MONDO:`/`OMIM:`) | `name`, `inheritance` | MONDO/OMIM/Orphanet / PrimeKG |

*(`Gene` and `Disease` could also be modeled as `Concept` subtypes; kept distinct for
clarity of the genetic layer and to reuse PrimeKG edges directly.)*

## Relationship types

| Relationship | From → To | Meaning |
|--------------|-----------|---------|
| `HAS_VISIT` | Patient → Visit | patient had this encounter |
| `DURING` | Condition/Drug/Measurement → Visit | event occurred within a visit |
| `NEXT_VISIT` | Visit → Visit | temporal ordering per patient (for density/trajectory) |
| `OF_CONCEPT` | instance event → Concept | anchors event to standardized meaning |
| `IS_A` | Concept → Concept | vocabulary hierarchy (SNOMED/LOINC/RxNorm subsumption) |
| `MAPS_TO` | Concept → Concept | cross-vocab / source→standard / HPO↔SNOMED bridge |
| `CAUSES` | Gene → Disease | causal gene–disease (genetic layer) |
| `HAS_PHENOTYPE` | Disease → Concept(HPO) | disease phenotype |
| `PATIENT_HAS_VARIANT` | Patient → Gene | genetic result (later phase; governed) |

## Temporal modeling

Time is central to every use case, so it is explicit:

- Every instance event carries a **date**; `NEXT_VISIT` chains order a patient's encounters.
- **First occurrence** of a feature = the earliest `ConditionOccurrence`/`Measurement`
  `OF_CONCEPT` a member of a feature concept set (used directly by the U1 delay metric).
- **Encounter density (U2)** = counts/spacing over `HAS_VISIT` + `NEXT_VISIT`, sliceable by
  `visit_concept_id` (inpatient/outpatient/ED).
- **Control trajectory (U3)** = ordered `Measurement.value_as_number` for a lab concept set
  (e.g., HbA1c) along the patient timeline.

## How the two layers serve reasoning

Because instance events are anchored to the backbone, a single query can traverse from a
gene, through disease phenotypes, to the standardized conditions actually observed in patients
— e.g., *"patients with a `TTR` `CAUSES` `ATTR` link whose earliest `OF_CONCEPT` into the ATTR
red-flag concept set precedes their ATTR diagnosis by > N months."* This is the structural
basis for the MVP in [`MVP_TTR.md`](MVP_TTR.md).

## Concept sets

Analytic definitions (red-flag features, diagnosis codes, drug classes, lab panels) are
expressed as **versioned concept sets** — lists of standard `concept_id`s (optionally
expanded down `IS_A` descendants). They live in code/config, are clinician-reviewable, and are
the unit we validate. This mirrors OHDSI ATLAS concept sets and keeps definitions explicit and
reproducible.
