# AIG-KG — Handoff & Project Notes

Snapshot for relocating the repo and resuming development on another machine / Claude Code CLI.

## Snapshot

- **Version:** 0.1.0 (tag `v0.1.0`; GitHub release published on the origin).
- **State:** prototype implemented, **11 tests green**, working tree clean.
- **Active branch:** `claude/emr-omop-kg-genetic-rnyw7r` (all work lives here; `main` on the
  origin is still the empty initial commit).
- **Origin at handoff:** `github.com/methionine23/AIG_KG` → relocating to
  `github.com/DLMP-Niu/…` (see "Moving the repo" below).

## What this project is

A **notebook-first NetworkX knowledge graph** over EMR data for **neurogenetic diseases**,
prototyped on **TTR/ATTR** (hereditary transthyretin amyloidosis). It represents real-world
diagnosis, evaluation, and management, and ships tools for four use cases. OMOP is the common
form so the same KG structure/tools also run over All of Us OMOP data in BigQuery later.

## Architecture (one screen)

- **Event contract** (`src/aig_kg/contract.py`) — every EMR table maps into one row shape
  (`person_id, domain, event_date, source_code/vocab/name, value_*, visit_id, …`). The builder
  and tools depend only on this, so the source (EMR download now, OMOP/BigQuery later) is
  swappable.
- **Graph backbone = Patient + date** (`src/aig_kg/graph/build.py`, `docs/DATA_MODEL.md`).
  Every event attaches to its `Patient` via `HAS_EVENT` and carries its own date. Links between
  events (`DURING` → visit) are **optional/best-effort** — tolerates outside-transferred
  diagnoses, meds without a visit, and virtual encounters. Two layers: instance events +
  ontology backbone (concepts + TTR→ATTR genetic layer).
- **Use-case tools** (`src/aig_kg/analytics/`): **U1** diagnostic delay · **U2** encounter
  density/care burden · **U3** comorbidity & control (diabetes/HbA1c) · **U4** CIDP-vs-mimic
  screen (operationalizes the Mayo CIDP calculator; ATTR is an explicit mimic → ties to U1).
- **Ingest** (`src/aig_kg/ingest/`) — loaders for the six real tables (demographics, diagnosis,
  encounter, appointment, lab, medication-orders) with cleanup. **Synth**
  (`src/aig_kg/synth/`) — deterministic PHI-free generator. **Notebook**
  (`notebooks/aig_kg_demo.ipynb`) — orchestration + visualization.

## Repo map

```
docs/           PROJECT_PLAN · DATA_MODEL · EMR_INPUT_SPEC · VOCABULARIES · MVP_TTR · USECASE_CIDP · PROTOTYPE
src/aig_kg/     contract · ingest · vocab · graph · analytics · synth · adapters(placeholder)
tests/          test_ingest · test_build · test_tools  (+ fixtures/*.tsv, synthetic)
notebooks/      aig_kg_demo.ipynb
environment.yml · requirements.txt · pyproject.toml
```

Design rationale and the full decisions log are in `docs/PROJECT_PLAN.md`.

## Resume on another machine

```bash
git clone <new-origin-url> AIG_KG && cd AIG_KG
git checkout claude/emr-omop-kg-genetic-rnyw7r     # or main, if the move makes it default
conda env create -f environment.yml && conda activate aig-kg   # or: pip install -r requirements.txt && pip install -e .
pytest -q                                          # expect 11 passed
jupyter notebook notebooks/aig_kg_demo.ipynb
```

Point the pipeline at real data by replacing `synth.generate()` with
`ingest.load_all("path/to/extracts")` (tab-delimited tables named like `tests/fixtures/*.tsv`).

## Data governance (important)

- **No PHI in git.** `data/raw`, `data/staging`, `data/vocab`, and `*.csv/*.parquet/*.duckdb`
  are git-ignored. Only synthetic `tests/fixtures/*.tsv` are committed.
- All of Us participant-level data **cannot leave the Workbench**; only aggregate results cross
  that boundary (`docs/PROJECT_PLAN.md` §9).

## Confirmed decisions

- `CURR_CLINIC` = unique patient ID; each table is its own source (cross-joins verified, not
  assumed). Encounter = canonical visit; appointment = secondary (density/specialty).
- Engine NetworkX (portable to the AoU Workbench); OMOP is the common form; Patient+date
  backbone; TTR/ATTR prototype scope; four use-case tools.

## Open items / next steps

1. **Run on real extracts** — adjust `ingest.load_*` to any header differences from the samples.
2. **U4 calibration** — the Mayo CIDP intercept/threshold isn't public; `cidp_probability` uses
   published odds ratios as weights with a placeholder intercept (flagged in code). EDX/exam
   variables need NCS/EMG or notes (NLP extension).
3. **U1 validation** against a chart-reviewed subset.
4. **OMOP/BigQuery source** — the second contract source for All of Us (`adapters/`).
5. **`main` branch** — currently empty on origin; decide whether the relocated repo's default
   branch should carry the code (recommended).

## Moving the repo (to DLMP-Niu)

Preserve full history + the `v0.1.0` tag with a mirror push (run where authenticated for the
destination):

```bash
# 1. Create an EMPTY repo DLMP-Niu/AIG_KG on GitHub (no README/license).
# 2. Mirror the current origin into it:
git clone --mirror https://github.com/methionine23/AIG_KG.git aig_kg.git
cd aig_kg.git
git push --mirror https://github.com/DLMP-Niu/AIG_KG.git
# 3. In the new repo: set default branch, and re-create the v0.1.0 GitHub Release from the tag
#    (the tag transfers with --mirror; the Release *object* is GitHub metadata and is re-made in the UI).
```

Alternatively, GitHub **Settings → Transfer ownership** moves the repo *with* issues/releases and
sets up redirects (but transfers rather than copies).
