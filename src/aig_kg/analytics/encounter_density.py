"""U2 — encounter density / care burden.

Counts and spacing of contact events (visits + appointments) per patient over their observed
window, sliced by modality (in-person vs virtual) and visit type. All from event dates.
"""
from __future__ import annotations

import pandas as pd

from aig_kg.graph import event_nodes, patient_ids

CONTACT_DOMAINS = {"visit", "appointment"}


def encounter_density(g, contact_domains=CONTACT_DOMAINS) -> pd.DataFrame:
    """One row per patient: contact count, span, rate/yr, mean gap, virtual share, ED count."""
    rows = []
    for pid in patient_ids(g):
        contacts = [g.nodes[n] for n in event_nodes(g, pid)
                    if g.nodes[n].get("domain") in contact_domains]
        dates = sorted(d["event_date"] for d in contacts if pd.notna(d.get("event_date")))
        if not dates:
            continue
        span_days = (dates[-1] - dates[0]).days
        span_years = span_days / 365.25 if span_days else 0.0
        gaps = [(b - a).days for a, b in zip(dates[:-1], dates[1:])]
        n_virtual = sum(1 for d in contacts if d.get("modality") == "virtual")
        n_ed = sum(1 for d in contacts if d.get("visit_type") == "ED")
        rows.append({
            "person_id": pid,
            "n_contacts": len(dates),
            "span_years": round(span_years, 2),
            "contacts_per_year": round(len(dates) / span_years, 2) if span_years else pd.NA,
            "mean_gap_days": round(sum(gaps) / len(gaps), 1) if gaps else pd.NA,
            "n_virtual": n_virtual,
            "virtual_share": round(n_virtual / len(dates), 2),
            "n_ED": n_ed,
        })
    return pd.DataFrame(rows)
