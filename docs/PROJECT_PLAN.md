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

**In scope (decided):**
- Input type A — **EMR table extracts** for diagnosis, encounters, medications, and labs.
  Each row carries at minimum: sample/patient ID, date, a name/code, a description, and a
  value (labs) or quantity/quality (meds).
- Input type B — **OMOP/SNOMED and All of Us survey/genomic data** (later phase; kept
  separate, harmonized by concept ID — see §9).
- A **two-layer graph**: patient-instance events linked into an **ontology backbone**
  (OMOP standard concepts + SNOMED/LOINC/RxNorm + HPO/gene/disease for the genetic layer).
- Analytics tools for the three use cases below.

**First milestone (decided):** **ATTR diagnostic delay** — measure latency from first
clinical feature to genetic testing/diagnosis in transthyretin amyloidosis patients.
See [`MVP_TTR.md`](MVP_TTR.md).

**Out of scope (for now):** building inside the All of Us secured Workbench (deferred; the
current data is local EMR extracts), a clinical-facing UI, and prospective/production use.

## 2. Use cases

| # | Use case | Core graph question | Key OMOP domains |
|---|----------|---------------------|------------------|
| U1 | **Diagnostic delay** *(MVP)* | Time from first red-flag feature → genetic dx/testing/therapy | condition, procedure, drug |
| U2 | **Encounter density / care burden** | Count/spacing/type of visits per patient & cohort over time | visit_occurrence |
| U3 | **Comorbidity & control** | Co-occurrence of conditions (e.g., diabetes) and control markers (glucose/HbA1c) trajectories | condition, measurement, drug |

All three share the same graph; they differ only in the analytics layer (§6, step 5).

## 3. Design principles

1. **OMOP relational layer is the source of truth; the graph is a projection.** We stage
   EMR extracts into an OMOP-CDM-shaped relational store first, then *project* that into the
   property graph. This keeps us reproducible, lets us reuse OHDSI tooling (e.g., ACHILLES
   data-density profiling for U2), and means the graph can always be rebuilt.
2. **Every concept node is keyed by a standard identifier** (OMOP `concept_id` + a CURIE such
   as `SNOMED:`, `LOINC:`, `RxNorm:`, `HP:`, `MONDO:`). This buys interoperability and a
   clean export path to RDF/FHIR-RDF or to ML embeddings later, without committing to those
   stacks now.
3. **Temporal-first.** Events are dated; the graph explicitly models ordering (first
   occurrence, next-visit chains) because every use case is fundamentally about *time*.
4. **No PHI in the repo.** Code and schema are versioned; patient-level data never is.

## 4. Technology recommendation (with justification)

You asked for a recommendation. Proposed stack for the MVP:

### Graph engine — **Neo4j (Community) + Graph Data Science (GDS) library**

**Why a property graph, and why Neo4j specifically:**
- **Trajectory analytics map to Cypher path queries.** "First red-flag feature before the
  diagnosis node," "shortest temporal path," and "events between visit A and visit B" are
  natural in Cypher and awkward in SQL or SPARQL.
- **GDS gives U2/U3 algorithms for free** — similarity, community detection, and centrality
  for patient-similarity, comorbidity clustering, and care-burden cohorting.
- **Schema-optional iteration** suits an evolving research model; we can add node/edge types
  without migrations.
- **Strong Python integration** (official `neo4j` driver; bulk load from pandas/`neo4j-admin
  import`).

**Why not RDF/OWL triplestore (for now):** formal OWL reasoning and SPARQL/FHIR-RDF interop
are valuable but not on the MVP critical path, and they add modeling overhead. We preserve the
option by keying every concept with a CURIE (principle 2), so an RDF export is a
transformation, not a rewrite. If ontology reasoning becomes central (e.g., inferring
phenotype subsumption), we revisit.

**Why not an ML-embedding-first stack (PyKEEN/PyG):** those optimize for link
prediction/GNNs, not interactive querying. Progression modeling is a likely later phase (§8,
Phase 4); when we get there we export the Neo4j graph to PyG — the two-layer model is already
GNN-friendly.

### Supporting stack

| Concern | Choice | Rationale |
|---|---|---|
| Language | **Python 3.11+** | Ecosystem for health data + Neo4j/PyG. |
| Relational staging | **DuckDB** (dev) → Postgres (scale) | Fast local CSV/Parquet + OMOP-shaped SQL; zero-setup for the MVP. |
| Vocabulary source | **OHDSI Athena** vocabulary tables | Canonical SNOMED/LOINC/RxNorm/ICD maps + `concept`/`concept_relationship`. |
| Genetic layer | **HPO, MONDO, OMIM/Orphanet**; reuse **PrimeKG** disease–gene–phenotype edges | Off-the-shelf backbone rather than hand-curating. |
| Graph→ML export | **PyG / PyKEEN** (later) | For Phase 4 progression models. |
| Orchestration | plain Python + `make`/CLI first; add a DAG tool only if needed | Avoid premature infra. |

### Prior art we build on (not from scratch)

- **OMOP CDM v5.4** — patient-centric schema and the vocabulary it standardizes onto.
- **PrimeKG / SPOKE** — disease–gene–phenotype backbone; SPOKE already demonstrates embedding
  EHR variables into a biomedical KG.
- **OHDSI ACHILLES** — data-density profiling, directly reusable for U2 (care burden).
- **ARCH / ChronoMedKG** — reference designs for codified+narrative and temporally-grounded
  clinical KGs, relevant when we add note-derived features and progression.

## 5. Architecture

```
 EMR extracts (CSV)                    OHDSI Athena vocab
 dx / enc / med / lab                 (concept, relationship)
        │                                     │
        ▼                                     ▼
 ┌──────────────┐   map source→standard  ┌──────────────┐
 │ 1. INGEST    │───────────────────────▶│ 2. VOCAB MAP │
 │ normalize    │                        │ concept_id + │
 │ to long form │                        │ CURIE        │
 └──────────────┘                        └──────┬───────┘
                                                 ▼
                                    ┌─────────────────────────┐
                                    │ 3. OMOP RELATIONAL STAGE │  ◀── source of truth
                                    │ (DuckDB): person,        │
                                    │ visit_occurrence,        │
                                    │ condition/drug/measurement│
                                    └────────────┬─────────────┘
                                                 ▼
                                    ┌─────────────────────────┐
                                    │ 4. GRAPH PROJECTION      │
                                    │ Neo4j: instance layer +  │
                                    │ ontology backbone        │
                                    └────────────┬─────────────┘
                                                 ▼
                                    ┌─────────────────────────┐
                                    │ 5. ANALYTICS             │
                                    │ U1 delay · U2 density ·  │
                                    │ U3 comorbidity/control   │
                                    └─────────────────────────┘
```

**Pipeline steps** (map to `src/aig_kg/` packages):
1. **Ingest** — read the four EMR table types, normalize to a common long event format
   (`person_id, event_date, domain, source_code, source_vocab, description, value, unit`).
2. **Vocab map** — resolve each source code to an OMOP standard `concept_id` + CURIE using
   Athena `concept`/`concept_relationship`; record unmapped codes for review.
3. **Stage** — load into an OMOP-shaped DuckDB (person, visit_occurrence, condition_occurrence,
   drug_exposure, measurement, observation). Canonical, queryable, reproducible.
4. **Project to graph** — build the two-layer property graph (see `DATA_MODEL.md`): instance
   nodes for patients/visits/events, backbone nodes for concepts, and edges linking them plus
   temporal ordering.
5. **Analytics** — per-use-case modules producing metrics/tables/figures.

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
| **P4 — Enrichment** | Genetic backbone + notes + ML | PrimeKG/HPO disease–gene–phenotype integration; optional NLP feature extraction from notes; PyG export + a progression baseline | Graph answers gene→phenotype→observed-dx paths; ML export works |
| **P5 — OMOP/All of Us** | Second data source | Reproducible in-Workbench build; concept-level harmonization with local KG | AoU component runs inside enclave, harmonized by concept_id |

## 8. Evaluation & validation

- **Data quality:** unmapped-code rate per domain; OHDSI Data Quality Dashboard-style checks;
  ACHILLES profiling on the staging layer.
- **U1 correctness:** validate a sample of computed delays against manual chart review where
  available; sanity-check feature/diagnosis concept sets with a clinician.
- **Reproducibility:** the graph can be rebuilt from staging + code; versioned concept sets.

## 9. Second data source (OMOP/SNOMED + All of Us) — deferred

All of Us data **cannot be exported** from its secured Researcher Workbench, so when we reach
P5 the KG build code runs *inside* the enclave and this repo holds only reproducible build
logic, never data. The two sources are **harmonized at the concept level** (shared OMOP
`concept_id`/CURIE) and **never merged at the raw-row level**. Survey data lands in the OMOP
`observation` domain and attaches to patient nodes like any other event.

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
| 2026-07-19 | Stack: Neo4j property graph projected from an OMOP DuckDB staging layer; Python. |
