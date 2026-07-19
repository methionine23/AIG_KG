# AIG-KG — Project Plan

*A knowledge graph for real-world diagnosis, evaluation, and management of genetic-disease
patients, built from EMR data and harmonized to OMOP/SNOMED.*

Last updated: 2026-07-19

---

## 1. Vision & scope

Flat EMR tables (one row per diagnosis, encounter, medication, lab) make it hard to ask
*trajectory* questions: when did a patient's illness actually begin, how long until it was
recognized, how heavily are they using the health system, and how do multiple conditions
compound over time. This project builds a **patient-trajectory knowledge graph** that sits
on top of standardized EMR data and makes those questions first-class.

**Deliverable (decided):** a **Python notebook + a small importable `aig_kg` script package**
that builds a **neurogenetic** knowledge graph. The scripts do the work (ingest, map, build,
analyze); the notebook is for **orchestration and visualization during development**, not for
hiding logic in cells.

**In scope (decided):**
- Input type A — **EMR table extracts** (local download) for diagnosis, encounters,
  medications, and labs. Each row carries at minimum: sample/patient ID, date, a name/code, a
  description, and a value (labs) or quantity/quality (meds).
- Input type B — **OMOP data, including All of Us** (OMOP-CDM in **BigQuery**, queried inside
  the Researcher Workbench). Handled through the *same* KG builder via a source adapter — not
  deferred. See §9.
- **OMOP is the common form and shared vocabulary** (§3): EMR-raw is mapped into OMOP once,
  All of Us is already OMOP, so both feed one builder producing structurally-identical KGs.
- A **two-layer graph** (in **NetworkX**): patient-instance events linked into an **ontology
  backbone** (OMOP standard concepts + SNOMED/LOINC/RxNorm + HPO/gene/disease for the
  genetic layer).
- **Use-case tools** (U1 delay, U2 density, U3 comorbidity/control) + an in-notebook **KG
  visualization explorer**.

**Prototype disease scope (decided):** **TTR / ATTR only** — one well-characterized
neurogenetic disease (hereditary ATTR polyneuropathy/cardiomyopathy) to prove the pipeline and
all three use cases end-to-end. The engine stays disease-configurable via concept sets, so
adding diseases later is data, not code.

**First milestone (decided):** **ATTR diagnostic delay** (U1) — latency from first clinical
feature to genetic testing/diagnosis. See [`MVP_TTR.md`](MVP_TTR.md).

**Out of scope (for now):** a clinical-facing UI, prospective/production use, and any
**physical merge** of local + All of Us data (prohibited by AoU export rules — §9).

## 2. Use cases

| # | Use case | Core graph question | Key OMOP domains |
|---|----------|---------------------|------------------|
| U1 | **Diagnostic delay** *(MVP)* | Time from first red-flag feature → genetic dx/testing/therapy | condition, procedure, drug |
| U2 | **Encounter density / care burden** | Count/spacing/type of visits per patient & cohort over time | visit_occurrence |
| U3 | **Comorbidity & control** | Co-occurrence of conditions (e.g., diabetes) and control markers (glucose/HbA1c) trajectories | condition, measurement, drug |

All three share the same graph; they differ only in the analytics layer (§6, step 5).

## 3. Design principles

1. **OMOP is the common form; the graph is a projection built by one shared builder.** Both
   sources become OMOP before the graph: EMR-raw is mapped into an OMOP-CDM-shaped store once,
   and All of Us is *already* OMOP in BigQuery. A single **KG builder** consumes OMOP through a
   pluggable **source adapter** (local DuckDB vs BigQuery), so the two environments produce
   **structurally-identical KGs** with the same vocabulary. This keeps us reproducible, lets us
   reuse OHDSI tooling (e.g., ACHILLES density profiling for U2), and means the graph can
   always be rebuilt.
2. **Every concept node is keyed by a standard identifier** (OMOP `concept_id` + a CURIE such
   as `SNOMED:`, `LOINC:`, `RxNorm:`, `HP:`, `MONDO:`). This buys interoperability and a
   clean export path to RDF/FHIR-RDF or to ML embeddings later, without committing to those
   stacks now.
3. **Temporal-first.** Events are dated; the graph explicitly models ordering (first
   occurrence, next-visit chains) because every use case is fundamentally about *time*.
4. **No PHI in the repo.** Code and schema are versioned; patient-level data never is.

## 4. Technology recommendation (with justification)

Chosen stack for the **notebook-first prototype** (must also run inside the AoU Workbench):

### Graph engine — **NetworkX (in-process, pip-installable)**

**Why NetworkX, not a graph server, for the prototype:**
- **Notebook-first + Workbench-portable.** It is pure Python, `pip`-installs anywhere, and runs
  identically on your local infra and inside the managed AoU Workbench VM — where standing up a
  Neo4j *server* is awkward. One codepath for both environments.
- **Visualization is first-class.** Pairs directly with `pyvis`/`matplotlib` for the
  in-notebook KG explorer and patient-trajectory views.
- **The analytics we need are graph-library-level** — first-occurrence, temporal ordering,
  neighbor/subgraph traversal, simple centrality — all straightforward in NetworkX over a
  cohort-sized graph.

**Deferred, not rejected — Neo4j + GDS for scale.** If graph size or algorithm richness
(community detection, large-scale similarity) outgrows in-memory NetworkX, we export to Neo4j.
Because every concept node is keyed by `concept_id` + CURIE (principle 2), that export — and an
RDF/FHIR-RDF or PyG/PyKEEN export for reasoning or GNNs — is a transformation, not a rewrite.

### Supporting stack

| Concern | Choice | Rationale |
|---|---|---|
| Language | **Python 3.11+** | Health-data ecosystem; runs in local + AoU notebooks. |
| Graph | **NetworkX** (+ `pyvis`/`matplotlib` for viz) | In-process, portable, viz-friendly. |
| OMOP staging (local) | **DuckDB** | Fast local CSV/Parquet + OMOP-shaped SQL; zero-setup. |
| OMOP source (AoU) | **BigQuery** via `google-cloud-bigquery` | Native CDR access inside the Workbench. |
| Vocabulary source | **OHDSI Athena** tables | Canonical SNOMED/LOINC/RxNorm/ICD maps. |
| Genetic layer | **HPO, MONDO, OMIM/Orphanet**; reuse **PrimeKG** edges | Off-the-shelf backbone. |
| Scale/ML export (later) | **Neo4j+GDS / PyG / PyKEEN** | Only if the prototype outgrows NetworkX. |

### Prior art we build on (not from scratch)

- **OMOP CDM v5.4** — patient-centric schema and the vocabulary it standardizes onto.
- **PrimeKG / SPOKE** — disease–gene–phenotype backbone; SPOKE already demonstrates embedding
  EHR variables into a biomedical KG.
- **OHDSI ACHILLES** — data-density profiling, directly reusable for U2 (care burden).
- **ARCH / ChronoMedKG** — reference designs for codified+narrative and temporally-grounded
  clinical KGs, relevant when we add note-derived features and progression.

## 5. Architecture

```
 SOURCE A: EMR raw download (CSV)        SOURCE B: All of Us (Workbench)
 dx / enc / med / lab                    OMOP-CDM in BigQuery
        │                                        │
        ▼ 1. INGEST + 2. VOCAB MAP               │  (already OMOP)
        │  (source→SNOMED/RxNorm/LOINC)          │
        ▼                                        ▼
 ┌───────────────────┐                 ┌───────────────────┐
 │ OMOP (local DuckDB)│                 │ OMOP (BigQuery)   │
 └─────────┬─────────┘                 └─────────┬─────────┘
           │      ── OMOP source adapter ──      │
           └──────────────┬──────────────────────┘
                          ▼
             ┌─────────────────────────┐   OHDSI Athena vocab +
             │ 3. KG BUILDER (shared)  │◀── HPO/MONDO/PrimeKG
             │ NetworkX: instance layer│    (ontology backbone)
             │ + ontology backbone     │
             └────────────┬────────────┘
                          ▼
             ┌─────────────────────────┐
             │ 4. USE-CASE TOOLS       │
             │ U1 delay · U2 density · │
             │ U3 comorbidity/control ·│
             │ KG viz explorer         │
             └─────────────────────────┘
```

Two structurally-identical KGs result (one per environment); only **aggregate results** cross
the AoU boundary (§9). The notebook drives steps 1–4 and renders the viz.

**Pipeline steps** (map to `src/aig_kg/` packages):
1. **Ingest** *(EMR source only)* — read the four EMR table types, normalize to a common long
   event format (`person_id, event_date, domain, source_code, source_vocab, description,
   value, unit`).
2. **Vocab map** *(EMR source only)* — resolve each source code to an OMOP standard
   `concept_id` + CURIE via Athena `concept`/`concept_relationship`; log unmapped codes.
   *(All of Us is already OMOP-coded and skips 1–2.)*
3. **Build KG** — one shared builder reads OMOP through a **source adapter** (DuckDB or
   BigQuery) and constructs the two-layer NetworkX graph (see `DATA_MODEL.md`): instance nodes
   for patients/visits/events, backbone nodes for concepts, and edges linking them plus
   temporal ordering.
4. **Use-case tools** — per-use-case modules (U1/U2/U3) + the viz explorer, producing
   metrics/tables/figures from the graph.

## 6. Repository structure

See `README.md`. Each pipeline step is a package under `src/aig_kg/`; docs under `docs/`;
patient-level data is git-ignored under `data/`.

## 7. Phased roadmap

| Phase | Goal | Key deliverables | Exit criteria |
|-------|------|------------------|---------------|
| **P0 — Plan** *(this)* | Agree scope, model, stack | This plan, data model, vocab strategy, MVP spec | Sign-off |
| **P1 — Backbone + ingest** | Stand up the pipeline on sample/synthetic data | Ingest for 4 table types; OMOP DuckDB staging; Athena vocab load; graph projection of instance + backbone layers; smoke tests | End-to-end run on Synthea/sample data produces a queryable graph |
| **P2 — MVP: ATTR delay (U1)** | Compute diagnostic delay | ATTR feature/dx concept sets; first-occurrence + latency queries; cohort output + figures; validation vs chart-review subset if available | Delay metric reproducible on real EMR extract |
| **P3 — Density & comorbidity (U2, U3)** | Care-burden + comorbidity analytics | Encounter-density metrics (ACHILLES-style); comorbidity co-occurrence + control-marker trajectories | U2 & U3 metrics on the same graph |
| **P4 — Enrichment / scale** | Genetic backbone + notes + scale | PrimeKG/HPO disease–gene–phenotype integration; optional NLP features from notes; NetworkX→Neo4j/PyG export if size demands | Graph answers gene→phenotype→observed-dx paths; scale export works |
| **P5 — All of Us (BigQuery)** | Second environment | Run the same builder + tools via the BigQuery adapter inside the Workbench; report aggregate results | AoU KG built in-Workbench from the shared code; aggregates match schema |

## 8. Evaluation & validation

- **Data quality:** unmapped-code rate per domain; OHDSI Data Quality Dashboard-style checks;
  ACHILLES profiling on the staging layer.
- **U1 correctness:** validate a sample of computed delays against manual chart review where
  available; sanity-check feature/diagnosis concept sets with a clinician.
- **Reproducibility:** the graph can be rebuilt from staging + code; versioned concept sets.

## 9. All of Us / OMOP source — access model & boundary

All of Us exposes its Curated Data Repository as **OMOP-CDM datasets in BigQuery**, queried
from Jupyter **inside the Researcher Workbench**. Two hard rules shape the design:

- **No participant-level data leaves the Workbench** (Data User Code of Conduct). The KG built
  from All of Us lives *inside* the Workbench; this repo holds only the reproducible build
  code, never data.
- **External data can't be cleanly joined to the CDR** (no CDR write access; temp-table
  limits). So we do **not** attempt a physical merge with the local EMR KG.

Instead, the **same `aig_kg` builder and use-case tools run in both environments** (they're
just Python + NetworkX + a BigQuery source adapter). Each produces a structurally-identical KG;
**only aggregate results** (delay distributions, density summaries, comorbidity rates — no
participant-level rows) cross the boundary, subject to AoU's review/export policy. This is how
point 3 — *one KG structure & vocabulary shared across EMR-raw and OMOP* — is satisfied without
violating export rules. Survey data lands in the OMOP `observation` domain and attaches to
patient nodes like any other event.

## 10. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Source codes map poorly to standard concepts | Track unmapped rate; keep source code on the node; clinician review of key concept sets |
| Diagnostic-delay definition is contestable | Make feature/dx concept sets explicit, versioned, and clinician-reviewed; report sensitivity to definition |
| PHI leakage | Git-ignore all patient-level data; no identifiers in commits; review before any external sharing |
| Over-engineering infra early | Start with DuckDB + plain Python; add scale/DAG tooling only when a real bottleneck appears |
| Vendor lock-in to Neo4j | Concept-keyed model + relational source of truth make RDF/PyG export a transform, not a rewrite |

## 11. Open decisions (to confirm as we go)

- Exact EMR extract schema/format (column names, code systems in the raw files) — will shape §5 step 1.
- Whether clinical **notes** are available for note-derived features (affects P4 and how early
  we can catch pre-diagnosis TTR red flags).
- Cohort/definition sign-off for the ATTR MVP from a clinical collaborator.
- Scale expectations (patient count) — determines DuckDB vs Postgres and Neo4j sizing.

---

### Decisions log

| Date | Decision |
|------|----------|
| 2026-07-19 | Data: local EMR extracts first; OMOP/All of Us later & separate. |
| 2026-07-19 | MVP use case: ATTR (TTR) diagnostic delay. |
| 2026-07-19 | Graph model: two-layer (patient instances + ontology backbone). |
| 2026-07-19 | ~~Stack: Neo4j property graph~~ → superseded 2026-07-19 (see below). |
| 2026-07-19 | Deliverable: a Python **notebook + `aig_kg` script package**; notebook for orchestration + viz. |
| 2026-07-19 | Engine: **NetworkX** (notebook-first, Workbench-portable); Neo4j/GDS deferred to scale. |
| 2026-07-19 | Cross-source: **OMOP is the common form**; one shared builder + source adapters (DuckDB / BigQuery); two structurally-identical KGs, never physically merged; only aggregates cross the AoU boundary. |
| 2026-07-19 | All of Us access confirmed: **OMOP-CDM in BigQuery** inside the Workbench (not deferred as an afterthought). |
| 2026-07-19 | Prototype disease scope: **TTR / ATTR only**, disease-configurable via concept sets. |
| 2026-07-19 | Prototype tools: **U1 delay, U2 density, U3 comorbidity/control, + KG viz explorer** (all four). |
