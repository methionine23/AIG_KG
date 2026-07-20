"""U3 — comorbidity & control.

Comorbidity co-occurrence (e.g., diabetes) and a control-marker trajectory (e.g., HbA1c) over
the patient timeline. Cohort defaults to everyone; pass a list of person_ids to restrict.
"""
from __future__ import annotations

import pandas as pd

from aig_kg.graph import dates_in_set, events_in_set, patient_ids


def _trajectory(g, pid, lab_set):
    pts = [(g.nodes[n]["event_date"], g.nodes[n].get("value_as_number"))
           for n in events_in_set(g, pid, lab_set)]
    pts = [(d, v) for d, v in pts if pd.notna(d) and pd.notna(v)]
    return sorted(pts)


def comorbidity_and_control(g, cohort=None, comorbidity_set="diabetes",
                            control_lab="hba1c") -> pd.DataFrame:
    """One row per patient: comorbidity present, and control-marker first/last/n + trajectory."""
    ids = cohort if cohort is not None else patient_ids(g)
    rows = []
    for pid in ids:
        has_comorbidity = len(dates_in_set(g, pid, comorbidity_set)) > 0
        traj = _trajectory(g, pid, control_lab)
        rows.append({
            "person_id": pid,
            f"has_{comorbidity_set}": has_comorbidity,
            f"n_{control_lab}": len(traj),
            f"first_{control_lab}": traj[0][1] if traj else pd.NA,
            f"last_{control_lab}": traj[-1][1] if traj else pd.NA,
            f"{control_lab}_trajectory": traj,   # list[(date, value)]
        })
    return pd.DataFrame(rows)
