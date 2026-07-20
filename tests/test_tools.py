import pandas as pd

from aig_kg import synth
from aig_kg.analytics import (
    cidp_probability,
    comorbidity_and_control,
    diagnostic_delay,
    encounter_density,
    screen_cidp_mimics,
)
from aig_kg.analytics.cidp import CIDP_ODDS_RATIOS
from aig_kg.graph import build_kg


def _graph(seed=2):
    person, events = synth.generate(seed=seed)
    return build_kg(person, events)


def test_u1_diagnostic_delay_positive_for_attr():
    g = _graph()
    df = diagnostic_delay(g)
    assert len(df) > 0
    delays = pd.to_numeric(df["delay_days_dx"], errors="coerce").dropna()
    assert (delays > 0).all()            # diagnosis always follows the first feature
    assert delays.median() > 365         # planted multi-year delay


def test_u2_encounter_density_reports_contacts_and_virtual_share():
    g = _graph()
    df = encounter_density(g)
    assert len(df) > 0
    assert (df["n_contacts"] >= 1).all()
    assert df["virtual_share"].between(0, 1).all()


def test_u3_comorbidity_and_control_finds_diabetes_trajectory():
    g = _graph()
    df = comorbidity_and_control(g)
    dm = df[df["has_diabetes"]]
    assert len(dm) > 0
    assert (dm["n_hba1c"] > 0).any()


def test_u4_screen_flags_cidp_mimics_for_workup():
    g = _graph()
    df = screen_cidp_mimics(g)
    assert len(df) > 0                    # synthetic CIDP-labeled patients exist
    assert df["recommend_genetic_workup"].any()
    assert (~df["has_attr_dx"]).all()     # mimics have no ATTR dx yet


def test_u4_probability_monotonic_in_features():
    base = cidp_probability({})
    one = cidp_probability({"progression_over_8wk": True})
    assert 0 <= base <= 1 and one > base
    allf = cidp_probability({k: True for k in CIDP_ODDS_RATIOS})
    assert allf > one
