"""Versioned concept sets for the TTR/ATTR prototype and the CIDP use case.

A ConceptSet matches an event by normalized code OR by a name keyword. Keyword matching lets us
handle local, un-crosswalked lab/med codes for the prototype; codes handle ICD diagnoses. Each
set is small, explicit, and clinician-reviewable — swap in Athena-expanded standard concept_ids
later without touching the tools.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from aig_kg.contract import normalize_code


@dataclass(frozen=True)
class ConceptSet:
    name: str
    codes: frozenset[str] = field(default_factory=frozenset)   # normalized codes
    name_keywords: tuple[str, ...] = ()                        # lowercase substrings
    note: str = ""

    def matches(self, source_code, source_name) -> bool:
        if normalize_code(source_code) in self.codes:
            return True
        n = (source_name or "").lower()
        return any(k in n for k in self.name_keywords)


def _cs(name, codes=(), keywords=(), note=""):
    return ConceptSet(name, frozenset(normalize_code(c) for c in codes), tuple(keywords), note)


# --- ATTR / TTR use case (U1) -------------------------------------------------------------
ATTR_DX = _cs(
    "attr_diagnosis",
    codes=["E85.82", "E85.81", "E85.4", "E85.9"],
    keywords=["amyloid", "transthyretin", "attr"],
    note="ATTR/amyloidosis diagnosis anchor (ICD10 E85.x + name).",
)
TTR_GENETIC_TEST = _cs(
    "ttr_genetic_test",
    keywords=["ttr gene", "transthyretin sequenc", "ttr sequenc", "amyloid genetic"],
    note="Genetic testing for TTR (often unstructured; keyword-based).",
)
ATTR_THERAPY = _cs(
    "attr_therapy",
    keywords=["tafamidis", "vyndaqel", "vyndamax", "patisiran", "onpattro",
              "inotersen", "tegsedi", "vutrisiran", "amvuttra"],
    note="Disease-specific ATTR therapy start (therapy anchor).",
)

# ATTR red-flag features (each precedes diagnosis; used as U1 'first feature')
REDFLAG_CARPAL_TUNNEL = _cs("rf_carpal_tunnel", codes=["G56.00", "G56.0", "354.0"],
                            keywords=["carpal tunnel"])
REDFLAG_POLYNEUROPATHY = _cs("rf_polyneuropathy", codes=["G62.9", "G60.9", "357.4"],
                             keywords=["polyneuropathy"])
REDFLAG_HF = _cs("rf_heart_failure", codes=["I50.31", "I50.30", "I50.9"],
                 keywords=["diastolic heart failure", "hfpef", "heart failure"])
REDFLAG_SPINAL_STENOSIS = _cs("rf_spinal_stenosis", codes=["M48.06", "M48.061"],
                              keywords=["spinal stenosis"])
REDFLAG_AUTONOMIC = _cs("rf_autonomic", codes=["G90.9", "G90.09"],
                        keywords=["autonomic"])

ATTR_REDFLAGS = (REDFLAG_CARPAL_TUNNEL, REDFLAG_POLYNEUROPATHY, REDFLAG_HF,
                 REDFLAG_SPINAL_STENOSIS, REDFLAG_AUTONOMIC)

# --- Comorbidity / control (U3) ------------------------------------------------------------
DIABETES_DX = _cs("diabetes", codes=["E11.9", "E10.9", "E11", "E10", "250.00"],
                  keywords=["diabetes"])
LAB_HBA1C = _cs("hba1c", codes=["A1C", "4548-4"], keywords=["a1c", "hemoglobin a1c"])
LAB_GLUCOSE = _cs("glucose", codes=["GLU", "1558-6"], keywords=["glucose"])

# --- CIDP use case (U4) --------------------------------------------------------------------
CIDP_DX = _cs("cidp_diagnosis", codes=["G61.81", "G61.82", "357.81"],
              keywords=["inflammatory demyelinating", "cidp"],
              note="CIDP diagnosis label (screen these for mimics).")
# EMR-derivable mimic red-flags that LOWER CIDP probability / suggest amyloid or inherited:
MIMIC_AUTONOMIC = REDFLAG_AUTONOMIC        # autonomic involvement argues against CIDP
MIMIC_MUSCLE_ATROPHY = _cs("muscle_atrophy", codes=["M62.50", "M62.5", "728.2"],
                           keywords=["muscle atrophy", "muscle wasting", "amyotrophy"])

REGISTRY = {cs.name: cs for cs in [
    ATTR_DX, TTR_GENETIC_TEST, ATTR_THERAPY,
    REDFLAG_CARPAL_TUNNEL, REDFLAG_POLYNEUROPATHY, REDFLAG_HF,
    REDFLAG_SPINAL_STENOSIS, REDFLAG_AUTONOMIC,
    DIABETES_DX, LAB_HBA1C, LAB_GLUCOSE,
    CIDP_DX, MIMIC_MUSCLE_ATROPHY,
]}


def get(name: str) -> ConceptSet:
    return REGISTRY[name]
