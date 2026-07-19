# AIG-KG — EMR + OMOP Knowledge Graph for Neurogenetic Diseases

A **Python notebook + `aig_kg` script package** that builds a knowledge graph to represent
**real-world diagnosis, evaluation, and management of neurogenetic-disease patients** from
electronic medical record (EMR) data, using **OMOP/SNOMED as the common form** so the *same*
KG structure and tools also run over **All of Us** OMOP data in BigQuery. The graph is built
in **NetworkX** (in-notebook, portable); the notebook is for orchestration and visualization.

The prototype targets **TTR / ATTR** (hereditary transthyretin amyloidosis) and answers
real-world questions that flat EMR tables answer poorly:

- **Diagnostic delay** — how long from the first clinical feature (e.g., a TTR patient's
  cardiac or neuropathy signs) to genetic testing and diagnosis. *(First milestone.)*
- **Encounter density / care burden** — intensity and pattern of healthcare contact per
  patient and cohort.
- **Compounding symptoms & control** — comorbidity trajectories (e.g., diabetes) and
  control markers (e.g., glucose/HbA1c) over time.

## Status

Design complete; prototype next. This repository currently contains the **project plan, data
model, and prototype spec**, not yet an implementation. Start here:

- [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) — vision, architecture, phased roadmap, and
  the technology recommendation with justification.
- [`docs/PROTOTYPE.md`](docs/PROTOTYPE.md) — the concrete build spec: package layout, source
  adapters, KG builder, use-case tool APIs, and the notebook flow.
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — the two-layer graph schema (patient instances +
  ontology backbone).
- [`docs/VOCABULARIES.md`](docs/VOCABULARIES.md) — clinical vocabulary and mapping strategy.
- [`docs/MVP_TTR.md`](docs/MVP_TTR.md) — the first milestone: measuring ATTR (transthyretin
  amyloidosis) diagnostic delay.

## Repository layout (proposed)

```
AIG_KG/
├── docs/                 # Design docs (this is where the plan lives)
├── notebooks/            # The deliverable notebook: orchestration + visualization
├── src/aig_kg/
│   ├── ingest/           # EMR table readers (diagnosis, encounter, med, lab) → long form
│   ├── vocab/            # Source→OMOP/SNOMED/LOINC/RxNorm/HPO concept mapping + concept sets
│   ├── adapters/         # OMOP source adapters: DuckDB (local) and BigQuery (All of Us)
│   ├── graph/            # Shared NetworkX KG builder (instance + ontology backbone)
│   └── analytics/        # Use-case tools: U1 delay, U2 density, U3 comorbidity/control, viz
├── data/
│   ├── raw/              # Input EMR extracts (git-ignored)
│   ├── staging/          # OMOP-shaped local DuckDB (git-ignored)
│   └── vocab/            # OHDSI vocabulary tables from Athena (git-ignored)
└── tests/
```

> **Data governance:** no PHI/patient-level data is committed. `data/raw/`, `data/vocab/`,
> and any patient-level artifacts are git-ignored. See the plan's governance section.
