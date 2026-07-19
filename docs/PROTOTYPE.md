# AIG-KG — Prototype Build Spec

The concrete, buildable shape of the prototype. It realizes the decisions in
[`PROJECT_PLAN.md`](PROJECT_PLAN.md): a **Python notebook + `aig_kg` package** that builds a
**TTR/ATTR** neurogenetic KG in **NetworkX** from **OMOP** (local DuckDB now, All of Us
BigQuery later via the same code), and ships **four use-case tools**.

## 1. What the prototype delivers

- `notebooks/aig_kg_demo.ipynb` — orchestrates the pipeline end-to-end and **visualizes** it:
  loads data → builds KG → runs U1/U2/U3 → renders the KG explorer. Thin cells that call the
  package; no business logic buried in the notebook.
- `src/aig_kg/` — importable package doing the real work (below).
- Runs on **synthetic data** out of the box (no PHI needed to develop), and on a real EMR
  download or All of Us by swapping the **source adapter**.

## 2. Package layout & responsibilities

```
src/aig_kg/
├── ingest/        # EMR-raw only: read dx/enc/med/lab CSV → common long-event DataFrame
├── vocab/         # source→OMOP concept mapping; TTR/ATTR concept sets (versioned)
├── adapters/      # OMOP source adapters → uniform OMOP DataFrames for the builder
│   ├── base.py        #   OMOPSource protocol
│   ├── duckdb_source.py   #   local OMOP in DuckDB
│   └── bigquery_source.py #   All of Us OMOP in BigQuery (Workbench)
├── graph/         # build_kg(): OMOP DataFrames → NetworkX two-layer graph
├── analytics/     # use-case tools (U1/U2/U3) + viz
│   ├── diagnostic_delay.py    # U1
│   ├── encounter_density.py   # U2
│   ├── comorbidity.py         # U3
│   └── viz.py                 # KG explorer (pyvis/matplotlib)
└── synth/         # tiny synthetic OMOP generator for dev/tests
```

**Flow:** `ingest`+`vocab` turn an EMR download into local OMOP (skipped when the source is
already OMOP) → an **adapter** yields uniform OMOP tables → `graph.build_kg()` builds the
NetworkX graph → `analytics.*` tools consume the graph.

## 3. Source adapter interface

One tiny protocol so the builder is source-agnostic. Each method returns a pandas DataFrame
with OMOP-standard columns (subset of CDM v5.4 needed for the prototype).

```python
# adapters/base.py
from typing import Protocol
import pandas as pd

class OMOPSource(Protocol):
    def person(self) -> pd.DataFrame: ...              # person_id, birth_year, sex_concept_id
    def visit_occurrence(self) -> pd.DataFrame: ...    # visit_occurrence_id, person_id, start/end, visit_concept_id
    def condition_occurrence(self) -> pd.DataFrame: ...# condition_occurrence_id, person_id, visit_id, date, condition_concept_id, source
    def drug_exposure(self) -> pd.DataFrame: ...       # drug_exposure_id, person_id, visit_id, start/end, drug_concept_id, quantity, source
    def measurement(self) -> pd.DataFrame: ...         # measurement_id, person_id, visit_id, date, measurement_concept_id, value_as_number, unit
    def concept(self, ids: set[int]) -> pd.DataFrame: ...  # concept_id, name, vocabulary_id, domain_id, standard_concept
```

- `DuckDBSource(path)` — reads a local OMOP DuckDB (built by `ingest`+`vocab`, or a Synthea→OMOP load).
- `BigQuerySource(project, dataset)` — reads the All of Us CDR; `concept()` queries the CDR
  `concept` table. Same return shapes, so the builder and tools don't change.

## 4. KG builder (NetworkX)

`graph/build_kg.py`:

```python
import networkx as nx
from aig_kg.adapters.base import OMOPSource

def build_kg(src: OMOPSource, concept_sets: "ConceptSets") -> nx.MultiDiGraph:
    """Build the two-layer graph (see DATA_MODEL.md).
    Instance nodes: Patient, Visit, ConditionOccurrence, DrugExposure, Measurement.
    Backbone nodes: Concept (+ Gene/Disease for the TTR layer).
    Edges: HAS_VISIT, DURING, NEXT_VISIT, OF_CONCEPT, IS_A, MAPS_TO, CAUSES, HAS_PHENOTYPE.
    """
```

Node identity and typing use NetworkX node attributes: a node key like `("Patient", person_id)`
or `("Concept", concept_id)`, with `data["label"]` = node type and standard `concept_id`/`curie`
on concept nodes. `NEXT_VISIT` edges are added by sorting each patient's visits by date. The
graph is a `MultiDiGraph` so multiple edge types can connect the same pair.

## 5. Use-case tools (the four)

Each is a plain function taking the graph (+ concept sets) and returning a tidy DataFrame the
notebook plots. Signatures (illustrative):

```python
# U1 — analytics/diagnostic_delay.py
def diagnostic_delay(g, cohort, redflags, anchors) -> pd.DataFrame:
    """Per patient: t(first redflag feature), t(anchor: dx/gene-test/therapy), delay_days,
    phenotype (cardiac/neuro-first). Aggregates: median/IQR by anchor & phenotype."""

# U2 — analytics/encounter_density.py
def encounter_density(g, cohort, window=None) -> pd.DataFrame:
    """Per patient/cohort: visit counts, mean inter-visit gap, counts by visit type
    (inpatient/outpatient/ED). Supports cohort-vs-comparison."""

# U3 — analytics/comorbidity.py
def comorbidity_and_control(g, cohort, comorbidity_set, control_lab) -> pd.DataFrame:
    """Comorbidity co-occurrence rate (e.g., diabetes) + control-marker trajectory
    (e.g., HbA1c value_as_number over time) per patient."""

# Viz — analytics/viz.py
def show_patient(g, person_id): ...     # one patient's trajectory subgraph (pyvis)
def show_backbone(g, disease="ATTR"): ...# gene→disease→phenotype→observed-dx backbone
```

The U1 tool is the MVP; its clinical definitions (red-flag / anchor concept sets) come from
`vocab` and are specified in [`MVP_TTR.md`](MVP_TTR.md).

## 6. Synthetic data for development

`synth/` generates a small OMOP dataset (~50–200 synthetic patients) with a plausible ATTR
signal: a subset get red-flag features (carpal tunnel, HFpEF, polyneuropathy) months-to-years
before an ATTR diagnosis / TTR test / tafamidis start, plus noise patients and some diabetes
comorbidity. This lets every tool and the viz run and be tested **without any real data**.
(Alternatively, load a Synthea export into the DuckDB source — a stretch option.)

## 7. Notebook flow (`aig_kg_demo.ipynb`)

1. **Config** — pick source (`DuckDBSource` on synthetic data by default), load concept sets.
2. **Build** — `g = build_kg(src, concept_sets)`; print node/edge counts by type.
3. **U1** — run `diagnostic_delay`; plot delay distribution + a couple of patient timelines.
4. **U2** — run `encounter_density`; plot burden curves / cohort comparison.
5. **U3** — run `comorbidity_and_control`; plot comorbidity rate + an HbA1c trajectory.
6. **Explore** — `show_patient(...)` and `show_backbone("ATTR")` interactive views.

## 8. Definition of done (prototype)

- One `pip install -e .` + `pytest` green on the synthetic dataset.
- The notebook runs top-to-bottom on synthetic data and renders all three tools + the explorer.
- Swapping `DuckDBSource` → `BigQuerySource` is the *only* change needed to target All of Us
  (adapter compiles against the same interface; not run here without Workbench access).
- Concept sets and the delay definition are explicit and versioned for clinician review.

## 9. Dependencies (prototype)

`networkx`, `pandas`, `duckdb`, `pyvis`, `matplotlib`, `pytest`; `google-cloud-bigquery` only
when using the All of Us adapter. Kept deliberately light so it installs cleanly in a local
venv and inside the AoU Workbench.
