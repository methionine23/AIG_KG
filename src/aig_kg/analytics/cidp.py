"""U4 — CIDP vs mimic scoring + misdiagnosis screen.

Operationalizes the Mayo CIDP probability calculator (Skolka et al., 2025, *Distinguishing
CIDP From Mimic Disorders*): a logistic model over six variables. ATTR amyloidosis is an
explicit mimic, so this ties directly to U1 (an "undiagnosed ATTR presenting as CIDP").

Two pieces:
1. ``cidp_probability`` — a transparent re-implementation using the *published odds ratios* as
   log-odds weights. NOTE: the paper's intercept is not published here, so the absolute
   probability/threshold must be calibrated before clinical interpretation. The default
   intercept is a placeholder; relative scoring (feature contributions) is faithful.
2. ``screen_cidp_mimics`` — KG-native: finds patients *labeled* CIDP and flags EMR-derivable
   mimic red-flags (autonomic involvement, muscle atrophy, ATTR features) for genetic/amyloid
   workup. Uses only structured EMR; EDX variables (ulnar CV/block) are typically unstructured
   and left as unknown.
"""
from __future__ import annotations

import math

import pandas as pd

from aig_kg.graph import events_in_set, patient_ids

# Published odds ratios (Skolka et al., 2025). Presence of each RAISES CIDP probability.
CIDP_ODDS_RATIOS = {
    "progression_over_8wk": 40.66,
    "absent_autonomic": 17.82,
    "absent_muscle_atrophy": 16.65,
    "proximal_weakness": 3.63,
    "ulnar_cv_slowing_lt_35_7": 5.21,
    "ulnar_conduction_block": 13.37,
}
# EDX variables not usually available as structured EMR.
EDX_FEATURES = {"ulnar_cv_slowing_lt_35_7", "ulnar_conduction_block"}

# Placeholder — MUST be calibrated to the paper to reproduce the 92% decision threshold.
DEFAULT_INTERCEPT = -6.0


def cidp_probability(features: dict, intercept: float = DEFAULT_INTERCEPT) -> float:
    """P(CIDP) from a feature dict {name: bool|None}. Unknown (None) contributes nothing.

    Uses log(OR) as each present feature's weight. See module note on intercept calibration.
    """
    logit = intercept
    for name, or_ in CIDP_ODDS_RATIOS.items():
        if features.get(name):            # True -> add weight; False/None -> add nothing
            logit += math.log(or_)
    return 1.0 / (1.0 + math.exp(-logit))


def _has(g, pid, set_name) -> bool:
    return len(events_in_set(g, pid, set_name)) > 0


def screen_cidp_mimics(g) -> pd.DataFrame:
    """One row per CIDP-labeled patient with EMR-derivable mimic red-flags and a workup flag."""
    rows = []
    for pid in patient_ids(g):
        if not _has(g, pid, "cidp_diagnosis"):
            continue
        autonomic = _has(g, pid, "rf_autonomic")
        muscle_atrophy = _has(g, pid, "muscle_atrophy")
        attr_features = sum(_has(g, pid, s) for s in
                            ("rf_carpal_tunnel", "rf_polyneuropathy", "rf_heart_failure",
                             "rf_spinal_stenosis"))
        has_attr_dx = _has(g, pid, "attr_diagnosis")

        # partial calculator inputs available from structured EMR (EDX left unknown)
        emr_features = {
            "absent_autonomic": not autonomic,
            "absent_muscle_atrophy": not muscle_atrophy,
        }
        rows.append({
            "person_id": pid,
            "cidp_labeled": True,
            "autonomic_involvement": autonomic,
            "muscle_atrophy": muscle_atrophy,
            "n_attr_features": attr_features,
            "has_attr_dx": has_attr_dx,
            # flag for workup: mimic signals present but no amyloid diagnosis yet
            "recommend_genetic_workup": (autonomic or muscle_atrophy or attr_features >= 1)
                                        and not has_attr_dx,
            "cidp_prob_partial": round(cidp_probability(emr_features), 3),
            "prob_is_partial": True,   # EDX + clinical exam variables not included
        })
    return pd.DataFrame(rows)
