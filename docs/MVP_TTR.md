# MVP — ATTR (Transthyretin Amyloidosis) Diagnostic Delay

**Goal:** quantify how long real-world ATTR patients wait between their **first clinical
red-flag feature** and their **genetic testing / diagnosis / disease-specific therapy** — the
"diagnostic odyssey" — using the two-layer graph.

ATTR is a strong first target: it is a genetic disease (hereditary ATTRv from *TTR* variants,
plus wild-type ATTRwt) with a well-documented diagnostic delay and a recognizable set of
*red-flag* features that typically appear **years before** diagnosis. That gap is exactly what
a trajectory graph can measure and flat tables cannot.

## Clinical background (definitions to be clinician-confirmed)

**Red-flag features** (often precede ATTR diagnosis; each becomes a concept set):
- Cardiac: HFpEF / heart failure, left-ventricular hypertrophy, low-voltage ECG, aortic stenosis.
- Neuro / MSK: bilateral **carpal tunnel syndrome**, **lumbar spinal stenosis**, biceps tendon
  rupture, peripheral **polyneuropathy**, autonomic dysfunction.
- (ATTRv often presents neuro-first, e.g., *TTR* p.V30M; ATTRwt / p.V142I often cardiac-first.)

**Diagnosis / confirmation events** (define the "diagnosed" timestamp):
- ICD/SNOMED **amyloidosis / ATTR** diagnosis code.
- **Genetic testing** for *TTR* (procedure or result).
- **Tc-99m PYP/DPD scan** (procedure), endomyocardial/fat-pad biopsy.
- **Disease-specific therapy** initiation: tafamidis, patisiran, inotersen, vutrisiran.

## Metric

For each ATTR-cohort patient:

```
delay = t(diagnosis anchor) − t(first red-flag feature)
```

Report multiple, explicitly-defined anchors (they answer different questions):
- **t_dx** — first ATTR diagnosis code.
- **t_gene** — first *TTR* genetic test.
- **t_therapy** — first disease-specific drug.

Outputs: distribution of `delay` (median/IQR), stratified by phenotype (cardiac vs neuro
first) and by anchor; count of red-flags accrued before diagnosis; per-patient timelines.

## Cohort definition

- **Cohort:** patients with an ATTR diagnosis concept, and/or a *TTR* genetic result, and/or
  disease-specific therapy. (Exact rule versioned as a concept set; clinician sign-off.)
- **Index/anchor:** as above.
- **Feature lookback:** all history before the anchor.

## Graph query sketch (NetworkX, date-anchored)

The metric is pure **date arithmetic over the patient's events** — no visit linkage required
(see `DATA_MODEL.md`, "Capturing timing"). For each patient, walk `HAS_EVENT`, keep events whose
`OF_CONCEPT` concept is in a concept set, and take the earliest date on each side.

```python
def delay_days(g, person_id, redflag_ids, anchor_ids):
    first_feature = min_event_date(g, person_id, redflag_ids)   # earliest red-flag event
    anchor        = min_event_date(g, person_id, anchor_ids)    # earliest dx / gene test / therapy
    if first_feature is None or anchor is None:
        return None
    return (anchor - first_feature).days

def min_event_date(g, person_id, concept_ids):
    dates = [g.nodes[ev]["event_date"]
             for ev in g.successors(("Patient", person_id))         # HAS_EVENT
             for c in g.successors(ev) if is_concept(c)             # OF_CONCEPT
             if concept_id_of(c) in concept_ids]
    return min(dates) if dates else None
```

*(`redflag_ids` / `anchor_ids` come from versioned concept sets, expanded down `IS_A`; concept
ids may be standard or `local:` codes for uncrosswalked lab/med tests.)*

## Steps to deliver (maps to roadmap P2)

1. Author + clinician-review the ATTR concept sets (red-flags, diagnosis, genetic test,
   therapies) with explicit `concept_id`s.
2. Build the ATTR cohort from the staged OMOP data.
3. Project the cohort into the graph (reusing the P1 pipeline).
4. Run the delay queries; produce distributions, stratifications, and per-patient timelines.
5. **Validate** a sample of computed delays against manual chart review where available;
   report sensitivity to concept-set/anchor choices.

## Success criteria

- A reproducible delay metric over the ATTR cohort, with explicit versioned definitions.
- Stratified results (phenotype, anchor) and a face-validity check with a clinician.
- The pipeline generalizes: swapping the concept sets yields the same analysis for another
  genetic disease with a known diagnostic delay.

## Known definitional risks

- "First feature" depends on the red-flag concept set — report sensitivity, don't hard-code one
  view.
- Codes may lag the true clinical onset (feature present in **notes** before it is coded);
  note-derived features (roadmap P4) can push the first-feature timestamp earlier and are a
  natural extension.
