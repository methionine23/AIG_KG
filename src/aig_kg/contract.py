"""The event contract: the single row shape every EMR source maps into.

Every raw table (diagnosis, encounter, appointment, lab, medication) is normalized to a
DataFrame with these columns. Domain-specific fields are null where they do not apply. The
KG builder consumes only this contract, so the graph and tools never depend on a particular
source (EMR download now, OMOP/BigQuery later).

See docs/EMR_INPUT_SPEC.md and docs/DATA_MODEL.md.
"""
from __future__ import annotations

# Domains and the node label each maps to in the graph.
DOMAINS = ("condition", "visit", "appointment", "drug", "measurement")

DOMAIN_TO_LABEL = {
    "condition": "ConditionEvent",
    "visit": "VisitEvent",
    "appointment": "AppointmentEvent",
    "drug": "DrugOrderEvent",
    "measurement": "MeasurementEvent",
}

# The unified event contract columns.
EVENT_COLUMNS = [
    "person_id",        # str  — CURR_CLINIC, the patient key (identical across tables)
    "domain",           # str  — one of DOMAINS
    "event_date",       # datetime — the reliable alignment key
    "end_date",         # datetime? — visit/therapy end where available
    "source_table",     # str  — provenance (which single source this row came from)
    "source_code",      # str  — code as it appears in the source
    "source_vocab",     # str  — ICD10CM / ICD9CM / HIC / local / ...
    "source_name",      # str  — human-readable name/description
    "value_as_number",  # float? — numeric lab result / dose
    "value_as_string",  # str?  — non-numeric result or med route/quality
    "unit",             # str?  — unit for value
    "visit_id",         # str?  — link to an encounter (best-effort; often null)
    "visit_type",       # str?  — inpatient / outpatient / ED (visit rows)
    "modality",         # str?  — in-person / virtual (visit/appointment rows)
    "specialty",        # str?  — clinical service (appointment rows)
    "is_primary",       # bool? — primary diagnosis flag (condition rows)
]

# The person/demographics contract.
PERSON_COLUMNS = ["person_id", "birth_year", "sex"]


def normalize_code(code) -> str:
    """Uppercase, strip, and drop the ICD dot so 'G56.00' and 'G5600' compare equal."""
    if code is None:
        return ""
    return str(code).strip().upper().replace(".", "")


def normalize_person_id(pid) -> str:
    return "" if pid is None else str(pid).strip()
