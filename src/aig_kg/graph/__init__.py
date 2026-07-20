"""Graph layer: build the two-layer NetworkX KG and query helpers.

Backbone is Patient + date (docs/DATA_MODEL.md): every event attaches to its Patient via
HAS_EVENT and carries its own date; DURING (event->visit) is best-effort. Query helpers read
event dates by concept set so the analytics tools stay tiny and schema-independent.
"""
from aig_kg.graph.build import (
    build_kg,
    dates_in_set,
    event_nodes,
    events_in_set,
    first_date_in_set,
    patient_ids,
)

__all__ = [
    "build_kg",
    "patient_ids",
    "event_nodes",
    "events_in_set",
    "dates_in_set",
    "first_date_in_set",
]
