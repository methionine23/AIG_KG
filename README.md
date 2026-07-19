# AIG-KG — EMR + OMOP Knowledge Graph for Genetic Diseases

A knowledge graph and toolset to represent **real-world diagnosis, evaluation, and
management of genetic-disease patients** using electronic medical record (EMR) data,
harmonized to OMOP/SNOMED and (in a later phase) All of Us survey + genomic data.

The graph is designed to answer real-world questions that flat EMR tables answer poorly:

- **Diagnostic delay** — how long from the first clinical feature (e.g., a TTR patient's
  cardiac or neuropathy signs) to genetic testing and diagnosis. *(First milestone.)*
- **Encounter density / care burden** — intensity and pattern of healthcare contact per
  patient and cohort.
- **Compounding symptoms & control** — comorbidity trajectories (e.g., diabetes) and
  control markers (e.g., glucose/HbA1c) over time.

## Status

Early design. This repository currently contains the **project plan and data model**,
not yet an implementation. Start here:

- [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) — vision, architecture, phased roadmap, and
  the technology recommendation with justification.
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — the two-layer graph schema (patient instances +
  ontology backbone).
- [`docs/VOCABULARIES.md`](docs/VOCABULARIES.md) — clinical vocabulary and mapping strategy.
- [`docs/MVP_TTR.md`](docs/MVP_TTR.md) — the first milestone: measuring ATTR (transthyretin
  amyloidosis) diagnostic delay.

## Repository layout (proposed)

```
AIG_KG/
├── docs/                 # Design docs (this is where the plan lives)
├── src/aig_kg/
│   ├── ingest/           # EMR table readers (diagnosis, encounter, med, lab)
│   ├── vocab/            # Source→OMOP/SNOMED/LOINC/RxNorm/HPO concept mapping
│   ├── graph/            # Graph schema + loaders (relational staging → property graph)
│   └── analytics/        # Use-case analytics (diagnostic delay, density, comorbidity)
├── data/
│   ├── raw/              # Input EMR extracts (git-ignored)
│   ├── staging/          # OMOP-shaped relational staging (canonical source of truth)
│   └── vocab/            # OHDSI vocabulary tables from Athena (git-ignored)
├── notebooks/            # Exploration
└── tests/
```

> **Data governance:** no PHI/patient-level data is committed. `data/raw/`, `data/vocab/`,
> and any patient-level artifacts are git-ignored. See the plan's governance section.
