# Use case U4 — CIDP vs mimic scoring & misdiagnosis screen

**Why it belongs here.** CIDP (chronic inflammatory demyelinating polyneuropathy) is the label
neurogenetic neuropathies are most often *mistaken* for — **ATTR amyloidosis is an explicit CIDP
mimic**. A patient carried for years as "CIDP" who is actually undiagnosed ATTR is exactly the
diagnostic-delay failure this project targets (ties directly to U1).

## The model we operationalize

Mayo's CIDP probability calculator (Skolka et al., 2025, *Distinguishing CIDP From Mimic
Disorders: The Role of Statistical Modeling*) — a logistic model over **six variables**, with
published odds ratios:

| Variable | OR | EMR-derivable? |
|---|---:|---|
| Progression over 8 weeks | 40.66 | partial (from event timing) |
| Absent autonomic involvement | 17.82 | yes (dx codes) |
| Absent muscle atrophy | 16.65 | yes (dx codes) |
| Proximal weakness | 3.63 | weak (exam, often unstructured) |
| Ulnar motor CV slowing < 35.7 m/s | 5.21 | no (EDX, unstructured) |
| Ulnar motor conduction block | 13.37 | no (EDX, unstructured) |

Reported operating point: ~92% probability threshold → 100% sensitivity, 68% specificity
(specificity rises with red-flags + EDX + labs).
Sources: [calculator](https://news.mayocliniclabs.com/cidp-calculator/),
[Skolka et al. (PubMed 39801067)](https://pubmed.ncbi.nlm.nih.gov/39801067/),
[amyloid neuropathy mimicking CIDP](https://pubmed.ncbi.nlm.nih.gov/22190302/).

## How the prototype implements it (`aig_kg.analytics.cidp`)

Two honest pieces:

1. **`cidp_probability(features, intercept)`** — a transparent re-implementation using each
   published **OR as a log-odds weight**. **Caveat:** the paper's *intercept* isn't in the
   abstract, so absolute probability and the 92% threshold need calibration before clinical use;
   the default intercept is a placeholder and is flagged as such. Relative contributions
   (which features move the score, and how much) are faithful to the published ORs.

2. **`screen_cidp_mimics(g)`** — the KG-native, EMR-only part. For every patient **labeled CIDP**
   it derives the structured-EMR mimic red-flags — autonomic involvement, muscle atrophy, and
   ATTR features (carpal tunnel, polyneuropathy, HF, spinal stenosis) — and flags
   `recommend_genetic_workup = (any mimic signal) AND (no ATTR diagnosis yet)`. EDX/exam
   variables are left `unknown` (typically unstructured), so the emitted `cidp_prob_partial` is
   explicitly marked partial.

## What it produces

One row per CIDP-labeled patient: the mimic red-flags found, whether an ATTR diagnosis already
exists, a workup recommendation, and a partial CIDP probability. In the synthetic cohort the
planted "CIDP mimic" patients (autonomic involvement ± muscle atrophy, ATTR features, no ATTR dx)
are correctly flagged.

## Honest limitations (prototype)

- **Intercept/threshold not calibrated** — do not read `cidp_prob_partial` as the official
  calculator output; it is a structural re-implementation pending the paper's constants.
- **EDX and exam findings are usually unstructured** — the strongest calculator variables
  (conduction block, CV slowing, proximal weakness, 8-week progression) need NCS/EMG reports or
  notes (a P4/NLP extension). The EMR screen is a *triage* signal, not a diagnosis.
- **Local code crosswalks** — CIDP/autonomic/atrophy concept sets are ICD-based here; local lab
  codes get LOINC/RxNorm crosswalks later without changing this tool.

## Roadmap fit

MVP-adjacent to U1: the misdiagnosis screen surfaces candidate undiagnosed-ATTR patients whose
"delay clock" (U1) is still running. Calibrating the full calculator and adding NLP-extracted
EDX/exam features are natural P2→P4 extensions.
