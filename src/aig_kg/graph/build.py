"""Build the two-layer property graph in NetworkX and provide small query helpers."""
from __future__ import annotations

import networkx as nx
import pandas as pd

from aig_kg.contract import DOMAIN_TO_LABEL
from aig_kg.vocab import REGISTRY, ConceptSet

# node-key helpers --------------------------------------------------------------------------
def _patient(pid: str) -> str: return f"patient:{pid}"
def _concept(vocab: str, code: str) -> str: return f"concept:{vocab}:{code}"
def _event(i: int) -> str: return f"event:{i}"

# minimal genetic backbone for the TTR/ATTR prototype
GENE_TTR = "gene:TTR"
DISEASE_ATTR = "disease:ATTR"


def build_kg(person_df: pd.DataFrame, events_df: pd.DataFrame,
             concept_sets: dict[str, ConceptSet] | None = None) -> nx.MultiDiGraph:
    """Construct the KG from a person table and an event-contract table.

    Nodes: Patient, one *Event per row (typed by domain), Concept (per source code), and the
    genetic backbone (Gene TTR -> Disease ATTR). Edges: HAS_EVENT (always), OF_CONCEPT,
    DURING (best-effort visit match), CAUSES.
    """
    cs = concept_sets or REGISTRY
    g = nx.MultiDiGraph()

    # patients
    for _, r in person_df.iterrows():
        g.add_node(_patient(r["person_id"]), kind="Patient",
                   person_id=r["person_id"], birth_year=r.get("birth_year"))

    # genetic backbone (small, fixed for the prototype)
    g.add_node(GENE_TTR, kind="Gene", symbol="TTR")
    g.add_node(DISEASE_ATTR, kind="Disease", name="ATTR amyloidosis", curie="MONDO:ATTR")
    g.add_edge(GENE_TTR, DISEASE_ATTR, key="CAUSES", type="CAUSES")

    visit_index: dict[str, str] = {}   # visit_id -> event node (for DURING)
    events = []

    for i, r in enumerate(events_df.itertuples(index=False)):
        row = r._asdict()
        pid = row["person_id"]
        patient = _patient(pid)
        if patient not in g:  # event references a patient absent from demographics — keep it
            g.add_node(patient, kind="Patient", person_id=pid, birth_year=None)

        matched = frozenset(name for name, c in cs.items()
                            if c.matches(row.get("source_code"), row.get("source_name")))
        node = _event(i)
        g.add_node(node, kind="Event", label=DOMAIN_TO_LABEL.get(row["domain"], "Event"),
                   concept_sets=matched, **{k: row.get(k) for k in (
                       "person_id", "domain", "event_date", "end_date", "source_table",
                       "source_code", "source_vocab", "source_name", "value_as_number",
                       "value_as_string", "unit", "visit_id", "visit_type", "modality",
                       "specialty", "is_primary")})
        g.add_edge(patient, node, key="HAS_EVENT", type="HAS_EVENT")
        events.append(node)

        # concept node + OF_CONCEPT (skip empty codes, e.g. bare visits)
        code = row.get("source_code")
        if pd.notna(code) and str(code).strip():
            vocab = row.get("source_vocab")
            vocab = "local" if pd.isna(vocab) else vocab
            cnode = _concept(vocab, code)
            if cnode not in g:
                g.add_node(cnode, kind="Concept", vocab=vocab,
                           code=code, name=row.get("source_name"))
            g.add_edge(node, cnode, key="OF_CONCEPT", type="OF_CONCEPT")

        if row["domain"] == "visit" and pd.notna(row.get("visit_id")):
            visit_index[str(row["visit_id"])] = node

    # DURING: best-effort link of dated events to a visit sharing visit_id
    for node in events:
        vid = g.nodes[node].get("visit_id")
        if pd.notna(vid) and g.nodes[node]["domain"] != "visit":
            target = visit_index.get(str(vid))
            if target is not None:
                g.add_edge(node, target, key="DURING", type="DURING")

    return g


# query helpers -----------------------------------------------------------------------------
def patient_ids(g: nx.MultiDiGraph) -> list[str]:
    return [d["person_id"] for _, d in g.nodes(data=True) if d.get("kind") == "Patient"]


def event_nodes(g: nx.MultiDiGraph, person_id: str):
    """All Event nodes for a patient (via HAS_EVENT)."""
    p = _patient(person_id)
    if p not in g:
        return []
    return [n for n in g.successors(p) if g.nodes[n].get("kind") == "Event"]


def events_in_set(g: nx.MultiDiGraph, person_id: str, set_name: str):
    return [n for n in event_nodes(g, person_id)
            if set_name in g.nodes[n].get("concept_sets", ())]


def dates_in_set(g: nx.MultiDiGraph, person_id: str, set_name: str) -> list[pd.Timestamp]:
    return [g.nodes[n]["event_date"] for n in events_in_set(g, person_id, set_name)
            if pd.notna(g.nodes[n].get("event_date"))]


def first_date_in_set(g: nx.MultiDiGraph, person_id: str, set_name: str):
    ds = dates_in_set(g, person_id, set_name)
    return min(ds) if ds else None
