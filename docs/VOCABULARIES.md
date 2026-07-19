# AIG-KG — Clinical Vocabularies & Mapping Strategy

The graph's power depends on anchoring messy source codes to **standard concepts**. We reuse
the OHDSI/OMOP vocabulary system rather than curating our own.

## Vocabularies by domain

| EMR extract | OMOP domain | Standard vocabulary | Notes |
|-------------|-------------|---------------------|-------|
| Diagnosis | Condition | **SNOMED CT** | Source ICD-10-CM/ICD-9-CM → SNOMED via OMOP maps |
| Encounter | Visit | OMOP **Visit** concepts | Inpatient / outpatient / ED / telehealth |
| Medication | Drug | **RxNorm / RxNorm Extension** | Source NDC/local → RxNorm ingredient/clinical drug; `quality`/quantity kept as properties |
| Lab | Measurement | **LOINC** | Source local lab codes → LOINC; values + units retained |
| Procedure (if present) | Procedure | **SNOMED / CPT4 / HCPCS** | e.g., genetic testing, PYP scan for ATTR |
| Survey (later) | Observation | **OMOP / LOINC / custom** | All of Us survey concepts |

## Genetic layer vocabularies

Not native to OMOP; integrated as backbone nodes and via bridge maps:

| Vocabulary | Use |
|------------|-----|
| **HPO** (Human Phenotype Ontology) | Phenotype features of genetic diseases (e.g., ATTR: polyneuropathy, cardiomyopathy, carpal tunnel) |
| **MONDO** | Unified disease identifiers; bridges OMIM/Orphanet/SNOMED disease concepts |
| **OMIM / Orphanet** | Mendelian/rare-disease gene–disease relations |
| **HGNC** | Canonical gene identifiers (e.g., `TTR`) |
| **PrimeKG** | Ready-made disease–gene–phenotype edges to seed the backbone |

The **HPO↔SNOMED** bridge (`MAPS_TO`) is what lets a disease's *phenotype* connect to the
*observed diagnosis codes* in patient data — the crux of the diagnostic-delay use case.

## Source of vocabulary data

- **OHDSI Athena** (`athena.ohdsi.org`) — download `concept`, `concept_relationship`,
  `concept_ancestor`, `relationship`, `vocabulary` tables (SNOMED, LOINC, RxNorm, ICD maps,
  etc.). Loaded into the DuckDB staging DB and mirrored as backbone `Concept` nodes.
- **OBO / MONDO / HPO** releases — for the genetic layer.
- **PrimeKG** release — for seed gene/disease/phenotype edges.

> Athena's SNOMED/RxNorm content requires accepting UMLS licensing; vocabulary files are
> **git-ignored** (`data/vocab/`) and downloaded per environment.

## Mapping procedure

For each source event:

1. Identify `source_vocab` (ICD-10-CM, NDC, local lab code, …) and `source_code`.
2. Look up the OMOP **source concept**, then follow `Maps to` in `concept_relationship` to the
   **standard concept** (`standard_concept = 'S'`).
3. Store both on the instance node: `source_code`/`source_vocab` (provenance) and
   `concept_id` + `curie` (for `OF_CONCEPT`).
4. If no map exists, mark **unmapped**, keep the source code, and log it. Track the unmapped
   rate per domain as a data-quality metric (see plan §8).

## Concept-set expansion

Analytic definitions expand a small set of seed `concept_id`s down `concept_ancestor` /`IS_A`
to include descendants (e.g., "all diabetes mellitus" or "all ATTR-related cardiomyopathy").
Sets are versioned in code and clinician-reviewable.

## Why this buys interoperability

Because every node carries a standard `concept_id` + CURIE:
- The graph can be **exported to RDF/FHIR-RDF** (CURIE → IRI) or to **PyG/PyKEEN** later
  without remodeling.
- A future **All of Us / OMOP** component harmonizes to the *same* concept space, so the two
  sources align at the concept level without merging raw rows (plan §9).
