"""KG visualization helpers. Heavy deps (pyvis/matplotlib) are imported lazily so the core
package installs without them.
"""
from __future__ import annotations

import pandas as pd

from aig_kg.graph import event_nodes
from aig_kg.graph.build import DISEASE_ATTR, GENE_TTR


def patient_timeline_df(g, person_id: str) -> pd.DataFrame:
    """Tidy, date-sorted event table for one patient — ready to plot as a timeline."""
    rows = []
    for n in event_nodes(g, person_id):
        d = g.nodes[n]
        rows.append({
            "event_date": d.get("event_date"),
            "domain": d.get("domain"),
            "name": d.get("source_name"),
            "code": d.get("source_code"),
            "value": d.get("value_as_number"),
            "concept_sets": sorted(d.get("concept_sets", ())),
        })
    df = pd.DataFrame(rows)
    return df.sort_values("event_date").reset_index(drop=True) if len(df) else df


def patient_subgraph(g, person_id: str):
    """Return the induced subgraph of a patient, their events, and the concepts they touch."""
    p = f"patient:{person_id}"
    if p not in g:
        return g.subgraph([])
    keep = {p, GENE_TTR, DISEASE_ATTR}
    for ev in event_nodes(g, person_id):
        keep.add(ev)
        keep.update(g.successors(ev))   # concepts / visits
    return g.subgraph(keep)


def to_pyvis(g, person_id: str, height: str = "600px"):
    """Interactive pyvis network for one patient (requires the 'viz' extra)."""
    try:
        from pyvis.network import Network
    except ImportError as e:  # pragma: no cover
        raise ImportError("pip install 'aig-kg[viz]' for interactive visualization") from e
    sub = patient_subgraph(g, person_id)
    net = Network(height=height, directed=True, notebook=True, cdn_resources="in_line")
    for n, d in sub.nodes(data=True):
        net.add_node(n, label=str(d.get("source_name") or d.get("symbol")
                                  or d.get("name") or d.get("kind")),
                     group=d.get("kind"))
    for u, v, d in sub.edges(data=True):
        net.add_edge(u, v, title=d.get("type"))
    return net
