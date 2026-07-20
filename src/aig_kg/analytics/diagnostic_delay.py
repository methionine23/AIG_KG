"""U1 — diagnostic delay: latency from first red-flag feature to the diagnosis anchor.

Pure date arithmetic over the patient's events (docs/MVP_TTR.md). Reports delay to each anchor
(diagnosis code, genetic test, therapy) and a cardiac-vs-neuro-first phenotype split.
"""
from __future__ import annotations

import pandas as pd

from aig_kg.graph import first_date_in_set, patient_ids

REDFLAG_SETS = ("rf_carpal_tunnel", "rf_polyneuropathy", "rf_heart_failure",
                "rf_spinal_stenosis", "rf_autonomic")
ANCHOR_SETS = {"dx": "attr_diagnosis", "gene": "ttr_genetic_test", "therapy": "attr_therapy"}
CARDIAC_SETS = ("rf_heart_failure",)
NEURO_SETS = ("rf_carpal_tunnel", "rf_polyneuropathy", "rf_autonomic")


def _min_date(g, pid, sets):
    ds = [d for d in (first_date_in_set(g, pid, s) for s in sets) if d is not None]
    return min(ds) if ds else None


def diagnostic_delay(g, redflag_sets=REDFLAG_SETS, anchor_sets=ANCHOR_SETS) -> pd.DataFrame:
    """One row per cohort patient (has any anchor), with delay_days to each anchor."""
    rows = []
    for pid in patient_ids(g):
        anchors = {k: first_date_in_set(g, pid, s) for k, s in anchor_sets.items()}
        if not any(v is not None for v in anchors.values()):
            continue  # not in the ATTR cohort
        first_feature = _min_date(g, pid, redflag_sets)
        cardiac = _min_date(g, pid, CARDIAC_SETS)
        neuro = _min_date(g, pid, NEURO_SETS)
        phenotype = "unknown"
        if cardiac and neuro:
            phenotype = "cardiac-first" if cardiac <= neuro else "neuro-first"
        elif cardiac:
            phenotype = "cardiac-first"
        elif neuro:
            phenotype = "neuro-first"

        row = {"person_id": pid, "first_feature": first_feature, "phenotype": phenotype}
        for k, adate in anchors.items():
            row[f"t_{k}"] = adate
            row[f"delay_days_{k}"] = (
                (adate - first_feature).days
                if adate is not None and first_feature is not None else pd.NA
            )
        rows.append(row)
    return pd.DataFrame(rows)
