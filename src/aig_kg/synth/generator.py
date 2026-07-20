"""Generate a small synthetic cohort (contract shape) with a planted ATTR/CIDP/diabetes signal.

Deterministic given ``seed`` so tests are stable. No PHI — fabricated ids and dates.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

import pandas as pd

from aig_kg.contract import EVENT_COLUMNS, PERSON_COLUMNS

_BASE = datetime(2010, 1, 1)


def _d(days: int) -> pd.Timestamp:
    return pd.Timestamp(_BASE + timedelta(days=days))


def generate(n_attr: int = 6, n_cidp_mimic: int = 4, n_diabetes: int = 6,
             n_noise: int = 10, seed: int = 0):
    """Return ``(person_df, events_df)`` with a mix of patient archetypes."""
    rng = random.Random(seed)
    persons, events = [], []

    def ev(pid, domain, day, table, code="", vocab="local", name="",
           num=None, sval=None, unit=None, visit_id=None, vtype=None, modality=None,
           specialty=None, primary=None):
        events.append({"person_id": pid, "domain": domain, "event_date": _d(day),
                       "end_date": None, "source_table": table, "source_code": code,
                       "source_vocab": vocab, "source_name": name, "value_as_number": num,
                       "value_as_string": sval, "unit": unit, "visit_id": visit_id,
                       "visit_type": vtype, "modality": modality, "specialty": specialty,
                       "is_primary": primary})

    def visits(pid, start, count, every, specialty="Neurology"):
        for k in range(count):
            day = start + k * every + rng.randint(-10, 10)
            virtual = rng.random() < 0.3
            ev(pid, "appointment", day, "appointment", name="Follow-up",
               modality="virtual" if virtual else "in-person", specialty=specialty)

    pid_n = 0

    def new_pid(prefix):
        nonlocal pid_n
        pid_n += 1
        pid = f"{prefix}{pid_n:03d}"
        persons.append({"person_id": pid, "birth_year": rng.randint(1940, 1975), "sex": None})
        return pid

    # ATTR patients: red flags -> diagnosis -> therapy, with a realistic delay
    for _ in range(n_attr):
        pid = new_pid("A")
        onset = rng.randint(200, 1200)
        delay = rng.randint(1000, 2500)          # ~3-7 yr diagnostic delay
        ev(pid, "condition", onset, "diagnosis", "G5600", "ICD10CM", "Carpal tunnel syndrome")
        ev(pid, "condition", onset + rng.randint(300, 900), "diagnosis", "G629", "ICD10CM",
           "Polyneuropathy unspecified")
        if rng.random() < 0.6:
            ev(pid, "condition", onset + rng.randint(600, 1200), "diagnosis", "I5031",
               "ICD10CM", "Diastolic heart failure")
        ev(pid, "condition", onset + delay, "diagnosis", "E8582", "ICD10CM",
           "Wild-type transthyretin amyloidosis", primary=True)
        ev(pid, "drug", onset + delay + rng.randint(5, 60), "medication", "MED0198", "local",
           "Tafamidis 61 mg capsule")
        visits(pid, onset, rng.randint(6, 14), rng.randint(120, 220))

    # CIDP mimics: labeled CIDP + mimic red flags, NO ATTR dx (should be flagged by U4)
    for _ in range(n_cidp_mimic):
        pid = new_pid("C")
        start = rng.randint(300, 1400)
        ev(pid, "condition", start, "diagnosis", "G6181", "ICD10CM",
           "Chronic inflammatory demyelinating polyneuritis", primary=True)
        ev(pid, "condition", start + rng.randint(30, 300), "diagnosis", "G909", "ICD10CM",
           "Autonomic dysfunction")
        if rng.random() < 0.5:
            ev(pid, "condition", start + rng.randint(60, 400), "diagnosis", "M6250",
               "ICD10CM", "Muscle atrophy")
        ev(pid, "condition", start + rng.randint(100, 500), "diagnosis", "G5600", "ICD10CM",
           "Carpal tunnel syndrome")
        visits(pid, start, rng.randint(5, 12), rng.randint(120, 200))

    # Diabetes patients: dx + HbA1c trajectory
    for _ in range(n_diabetes):
        pid = new_pid("D")
        start = rng.randint(200, 1500)
        ev(pid, "condition", start, "diagnosis", "E119", "ICD10CM",
           "Type 2 diabetes mellitus", primary=True)
        base_a1c = rng.uniform(7.5, 10.0)
        for k in range(rng.randint(3, 6)):
            a1c = max(5.5, base_a1c - k * rng.uniform(0.2, 0.8))
            ev(pid, "measurement", start + k * 180, "lab", "A1C", "local",
               "Hemoglobin A1c", num=round(a1c, 1), unit="%")
        visits(pid, start, rng.randint(4, 10), rng.randint(150, 250), specialty="Endocrinology")

    # Noise patients
    for _ in range(n_noise):
        pid = new_pid("N")
        start = rng.randint(200, 1600)
        ev(pid, "condition", start, "diagnosis", "M545", "ICD10CM", "Low back pain")
        ev(pid, "measurement", start + 30, "lab", "GLU", "local", "Glucose fasting",
           num=round(rng.uniform(80, 110), 0), unit="mg/dL")
        visits(pid, start, rng.randint(2, 6), rng.randint(180, 300), specialty="Primary Care")

    person_df = pd.DataFrame(persons, columns=PERSON_COLUMNS)
    events_df = pd.DataFrame(events, columns=EVENT_COLUMNS)
    return person_df, events_df
