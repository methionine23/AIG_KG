from aig_kg import synth
from aig_kg.graph import build_kg, event_nodes, patient_ids


def test_build_from_synth_has_layers_and_edges():
    person, events = synth.generate(seed=1)
    g = build_kg(person, events)

    kinds = {d.get("kind") for _, d in g.nodes(data=True)}
    assert {"Patient", "Event", "Concept", "Gene", "Disease"} <= kinds

    # every event is reachable from its patient via HAS_EVENT
    total_events = sum(len(event_nodes(g, pid)) for pid in patient_ids(g))
    assert total_events == len(events)

    # backbone edge present
    assert g.has_edge("gene:TTR", "disease:ATTR")

    # events carry concept-set membership (at least the ATTR anchor appears somewhere)
    assert any("attr_diagnosis" in g.nodes[n].get("concept_sets", ())
               for n in g.nodes if g.nodes[n].get("kind") == "Event")


def test_during_edges_are_optional_and_present_when_visit_matches():
    # fixtures: diagnoses carry Visit_Nbr that matches encounter rows
    import os

    from aig_kg import ingest
    fix = os.path.join(os.path.dirname(__file__), "fixtures")
    person, events = ingest.load_all(fix)
    g = build_kg(person, events)
    during = [(u, v) for u, v, k in g.edges(keys=True) if k == "DURING"]
    assert len(during) >= 1   # at least one diagnosis links to its encounter
