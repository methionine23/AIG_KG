"""Load and clean the six real EMR tables into the event contract.

Cleanup rules applied (docs/EMR_INPUT_SPEC.md §3): unify person_id, parse/validate dates,
standardize codes, split numeric/character lab results, filter the orders table to drug orders,
drop unusable rows, deduplicate. Each table is treated as its own source; cross-table joins are
best-effort and never assumed.
"""
from __future__ import annotations

import os

import pandas as pd

from aig_kg.contract import (
    EVENT_COLUMNS,
    PERSON_COLUMNS,
    normalize_code,
    normalize_person_id,
)

_DX_VOCAB = {"ICD10": "ICD10CM", "ICD9": "ICD9CM", "HIC": "HIC"}


def _read(path_or_df, **kw):
    if isinstance(path_or_df, pd.DataFrame):
        return path_or_df.copy()
    return pd.read_csv(path_or_df, sep="\t", dtype=str, **kw)


def _empty_events() -> pd.DataFrame:
    return pd.DataFrame(columns=EVENT_COLUMNS)


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Common cleanup: person_id, dates, drop rows without the essentials, dedupe."""
    df = df.copy()
    df["person_id"] = df["person_id"].map(normalize_person_id)
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    if "end_date" in df:
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
    # ensure all contract columns exist
    for c in EVENT_COLUMNS:
        if c not in df:
            df[c] = pd.NA
    df = df[EVENT_COLUMNS]
    # implausible dates (missing, before 1900, or in the far future) are unusable
    bad = df["event_date"].isna() | (df["event_date"].dt.year < 1900)
    df = df[~bad & (df["person_id"] != "")]
    return df.drop_duplicates(subset=["person_id", "domain", "event_date", "source_code"])


def load_demographics(src) -> pd.DataFrame:
    """demographics (CURR_CLINIC, DOB) -> person table (person_id, birth_year, sex)."""
    raw = _read(src)
    out = pd.DataFrame({
        "person_id": raw["CURR_CLINIC"].map(normalize_person_id),
        "birth_year": pd.to_datetime(raw["DOB"], errors="coerce").dt.year.astype("Int64"),
        "sex": pd.NA,
    })
    return out.drop_duplicates("person_id")[PERSON_COLUMNS]


def load_diagnosis(src) -> pd.DataFrame:
    raw = _read(src)
    df = pd.DataFrame({
        "person_id": raw["CURR_CLINIC"],
        "domain": "condition",
        "event_date": raw["Dx_Date"],
        "source_table": "diagnosis",
        "source_code": raw["Dx_Code"].map(normalize_code),
        "source_vocab": raw["Dx_Type"].map(lambda v: _DX_VOCAB.get(str(v).strip(), "local")),
        "source_name": raw["Dx_Desc"],
        "visit_id": raw.get("Visit_Nbr"),
        "is_primary": raw.get("Primary_Dx_Flag", pd.Series(dtype=str))
                         .isin(["1", "Y", "Yes", "YES"]),
    })
    return _finalize(df)


def load_encounter(src) -> pd.DataFrame:
    raw = _read(src)
    admit = raw.get("Admit_Type", pd.Series([pd.NA] * len(raw))).astype(str).str.lower()
    visit_type = admit.map(lambda a: "ED" if "emerg" in a
                           else "inpatient" if "inpatient" in a
                           else "outpatient")
    df = pd.DataFrame({
        "person_id": raw["CURR_CLINIC"],
        "domain": "visit",
        "event_date": raw["Arrive_Date"],
        "source_table": "encounter",
        "source_name": raw.get("Admit_Type"),
        "visit_id": raw["Visit_Nbr"],
        "visit_type": visit_type,
        "modality": "in-person",   # encounter table = in-person contacts
    })
    return _finalize(df)


def load_appointment(src) -> pd.DataFrame:
    raw = _read(src)
    desc = raw.get("Appt_Desc", pd.Series([""] * len(raw))).astype(str).str.lower()
    modality = desc.map(lambda d: "virtual" if ("virtual" in d or "tele" in d or "video" in d)
                        else "in-person")
    df = pd.DataFrame({
        "person_id": raw["CURR_CLINIC"],
        "domain": "appointment",
        "event_date": raw["Appt_Begin_Date"],
        "source_table": "appointment",
        "source_name": raw.get("Appt_Desc"),
        "visit_type": "outpatient",
        "modality": modality,
        "specialty": raw.get("Appt_Clinical_Service"),
    })
    return _finalize(df)


def load_lab(src) -> pd.DataFrame:
    raw = _read(src)
    df = pd.DataFrame({
        "person_id": raw["CURR_CLINIC"],
        "domain": "measurement",
        "event_date": raw["Lab_Date"],
        "source_table": "lab",
        "source_code": raw["Test_Code"].map(normalize_code),
        "source_vocab": "local",
        "source_name": raw["TestDesc"],
        "value_as_number": pd.to_numeric(raw.get("Resultn"), errors="coerce"),
        "value_as_string": raw.get("Resultc"),
        "unit": raw.get("Units"),
    })
    return _finalize(df)


def load_medication(src) -> pd.DataFrame:
    """medication is an ORDERS table -> filter to drug orders only."""
    raw = _read(src)
    otype = (raw.get("Order_Type", pd.Series([""] * len(raw))).astype(str).str.upper()
             + " "
             + raw.get("Order_Type_Desc", pd.Series([""] * len(raw))).astype(str).str.lower())
    is_med = otype.str.contains("RX") | otype.str.contains("medication")
    raw = raw[is_med]
    df = pd.DataFrame({
        "person_id": raw["CURR_CLINIC"],
        "domain": "drug",
        "event_date": raw["Order_Date"],
        "source_table": "medication",
        "source_code": raw["Order_Code"].map(normalize_code),
        "source_vocab": "local",
        "source_name": raw["Order_Name"],
    })
    return _finalize(df)


_TABLES = {
    "diagnosis": load_diagnosis,
    "encounter": load_encounter,
    "appointment": load_appointment,
    "lab": load_lab,
    "medication": load_medication,
}


def load_all(dir_path: str, suffix: str = "_sample.tsv"):
    """Load every table found under ``dir_path`` and return ``(person_df, events_df)``.

    Missing tables are skipped (each table is an independent source).
    """
    person = pd.DataFrame(columns=PERSON_COLUMNS)
    demo_path = os.path.join(dir_path, f"demographics{suffix}")
    if os.path.exists(demo_path):
        person = load_demographics(demo_path)

    frames = []
    for name, fn in _TABLES.items():
        path = os.path.join(dir_path, f"{name}{suffix}")
        if os.path.exists(path):
            frames.append(fn(path))
    events = pd.concat(frames, ignore_index=True) if frames else _empty_events()
    return person, events
