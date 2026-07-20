"""Use-case tools computed over the KG.

U1 diagnostic_delay · U2 encounter_density · U3 comorbidity_and_control · U4 CIDP mimic screen.
Each returns a tidy pandas DataFrame the notebook plots. All timing is date arithmetic over
HAS_EVENT (no visit linkage required).
"""
from aig_kg.analytics.cidp import cidp_probability, screen_cidp_mimics
from aig_kg.analytics.comorbidity import comorbidity_and_control
from aig_kg.analytics.diagnostic_delay import diagnostic_delay
from aig_kg.analytics.encounter_density import encounter_density

__all__ = [
    "diagnostic_delay",
    "encounter_density",
    "comorbidity_and_control",
    "cidp_probability",
    "screen_cidp_mimics",
]
