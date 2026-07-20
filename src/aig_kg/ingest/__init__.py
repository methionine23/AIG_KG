"""Ingest layer: read the six EMR tables and normalize to the event contract.

Each ``load_*`` maps one real source table into contract columns (see docs/EMR_INPUT_SPEC.md).
``load_all`` runs them over a directory of TSV extracts and returns ``(person_df, events_df)``
ready for the KG builder.
"""
from aig_kg.ingest.loaders import (
    load_all,
    load_appointment,
    load_demographics,
    load_diagnosis,
    load_encounter,
    load_lab,
    load_medication,
)

__all__ = [
    "load_all",
    "load_demographics",
    "load_diagnosis",
    "load_encounter",
    "load_appointment",
    "load_lab",
    "load_medication",
]
