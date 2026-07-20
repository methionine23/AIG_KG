import os

import pandas as pd

from aig_kg import ingest

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def test_load_all_returns_person_and_events():
    person, events = ingest.load_all(FIX)
    assert set(person["person_id"]) >= {"P001", "P002", "P003", "P004"}
    assert len(events) > 0


def test_diagnosis_cleanup_drops_bad_date_and_dedupes():
    dx = ingest.load_diagnosis(os.path.join(FIX, "diagnosis_sample.tsv"))
    # 10 raw rows -> drop the NA-date row and collapse the P002 duplicate = 8
    assert len(dx) == 8
    # whitespace id normalized
    assert "P002 " not in set(dx["person_id"])
    # ICD dot removed
    assert "G5600" in set(dx["source_code"])
    # per-row vocabulary from Dx_Type
    assert set(dx["source_vocab"]) >= {"ICD10CM", "ICD9CM", "HIC"}


def test_medication_orders_filtered_to_drugs():
    med = ingest.load_medication(os.path.join(FIX, "medication_sample.tsv"))
    names = " ".join(med["source_name"].tolist()).lower()
    assert "tafamidis" in names
    assert "echocardiogram" not in names          # IMG order excluded
    assert (med["domain"] == "drug").all()


def test_lab_numeric_and_string_split():
    lab = ingest.load_lab(os.path.join(FIX, "lab_sample.tsv"))
    a1c = lab[lab["source_code"] == "A1C"]
    assert pd.to_numeric(a1c["value_as_number"]).notna().all()
    trop = lab[lab["source_code"] == "TROP"].iloc[0]
    assert pd.isna(trop["value_as_number"]) and trop["value_as_string"] == "<0.01"
