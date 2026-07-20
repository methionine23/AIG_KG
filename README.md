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

**Prototype implemented.** The `aig_kg` package builds the TTR/ATTR KG from EMR extracts (or
synthetic data) and ships the four use-case tools; a demo notebook orchestrates and visualizes
it. 11 tests pass.

### Quickstart

```bash
pip install -e .            # core (pandas, networkx);  add [viz] for pyvis/matplotlib
pytest -q                   # 11 tests, synthetic + fixtures
jupyter notebook notebooks/aig_kg_demo.ipynb
```

```python
from aig_kg import synth, ingest
from aig_kg.graph import build_kg
from aig_kg.analytics import diagnostic_delay, encounter_density, comorbidity_and_control, screen_cidp_mimics

person, events = synth.generate()                 # or: ingest.load_all("path/to/extracts")
g = build_kg(person, events)
diagnostic_delay(g)        # U1   encounter_density(g)          # U2
comorbidity_and_control(g) # U3   screen_cidp_mimics(g)         # U4
```

### Docs

- [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) — vision, architecture, phased roadmap, and
  the technology recommendation with justification.
- [`docs/PROTOTYPE.md`](docs/PROTOTYPE.md) — the concrete build spec: package layout, source
  adapters, KG builder, use-case tool APIs, and the notebook flow.
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — the two-layer graph schema (patient + date
  backbone; optional event links).
- [`docs/EMR_INPUT_SPEC.md`](docs/EMR_INPUT_SPEC.md) — the event contract, per-table column
  mapping for the real schema, cleanup checklist, and testing strategy.
- [`docs/VOCABULARIES.md`](docs/VOCABULARIES.md) — clinical vocabulary and mapping strategy.
- [`docs/MVP_TTR.md`](docs/MVP_TTR.md) — U1: measuring ATTR diagnostic delay.
- [`docs/USECASE_CIDP.md`](docs/USECASE_CIDP.md) — U4: CIDP-vs-mimic scoring & misdiagnosis
  screen (operationalizes the Mayo CIDP calculator).

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
