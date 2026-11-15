from datetime import timedelta
import pytest
from rematch.common.clock import T0
from rematch.common.schemas import Criterion, FieldFact
from rematch.clinic.matching.evaluators import evaluate
from rematch.clinic.matching.engine import match
from rematch.clinic.matching.snapshot import PatientSnapshot
from scripts.build_trial_fixtures import build_trials


def fact(key="hba1c", value=9.1, age=0, unit="%", method="HPLC"):
    return FieldFact(field=key, value=value, unit=unit, effective_date=T0-timedelta(days=age),
                     method=method, source_resource_id=f"test-{key}")


def hero_snapshot(hba1c=11.2):
    return PatientSnapshot.from_facts("hero", [fact("age", 58, unit="years"), fact(value=hba1c),
        fact("egfr", 71, unit="mL/min/1.73m2"), fact("bmi", 31, unit="kg/m2"),
        *[fact(k, v, unit=None) for k, v in {"dx_t2dm": True, "rx_metformin": True, "rx_insulin": False, "pregnant": False}.items()]])


@pytest.mark.parametrize("kind,value,age,expected", [
    ("inclusion", 9, 0, "MET"), ("inclusion", 11, 0, "NOT_MET"),
    ("exclusion", 9, 0, "NOT_MET"), ("exclusion", 11, 0, "MET"),
    ("inclusion", None, 0, "UNKNOWN"), ("exclusion", None, 0, "UNKNOWN"),
    ("inclusion", 9, 91, "UNKNOWN"), ("exclusion", 9, 91, "UNKNOWN")])
def test_engine_truth_tables(kind, value, age, expected):
    c = build_trials()[0].criteria[2].model_copy(update={"type": kind})
    assert evaluate(c, None if value is None else fact(value=value, age=age), T0).status == expected


@pytest.mark.parametrize("value,expected", [(7.5,"POTENTIAL_MATCH"),(10,"POTENTIAL_MATCH"),(10.01,"NOT_MATCHED"),(11.2,"NOT_MATCHED"),(9.1,"POTENTIAL_MATCH")])
def test_hero_and_boundaries(value, expected):
    result = match(hero_snapshot(value), build_trials()[0], T0)
    assert result.status == expected
    if value > 10:
        assert result.blocking_criteria == ["SYN-0001-C3"]
        assert result.watch
    assert result.criteria[-1].reason == "SCREENING_ONLY"
    assert result.criteria[-1].reuse_class == "REPEAT_REQUIRED"


def test_staleness_unmapped_and_conversion():
    trial = build_trials()[0]
    assert match(hero_snapshot(9.1), trial, T0+timedelta(days=91)).status == "NEEDS_INFO"
    c = trial.criteria[2]
    assert evaluate(c, fact(unit="mmol/mol", value=(9.1-2.15)*10.929), T0).status == "MET"
    assert "UNIT_CONVERTED" in evaluate(c, fact(unit="mmol/mol", value=70), T0).explanation
    assert evaluate(c, fact(unit="garbage"), T0).reason == "UNIT_MISMATCH"
    assert evaluate(c.model_copy(update={"field":"unmapped"}), None, T0).reason == "UNMAPPED"
    assert evaluate(c, fact(age=-1), T0).reason == "FUTURE"


def test_insulin_has_no_watch():
    snapshot = hero_snapshot(9.1)
    snapshot.facts["rx_insulin"] = fact("rx_insulin", True, unit=None)
    assert not match(snapshot, build_trials()[0], T0).watch


def test_missing_boolean_is_unknown():
    snapshot = hero_snapshot(9.1)
    del snapshot.facts["rx_insulin"]
    assert match(snapshot, build_trials()[0], T0).status == "NEEDS_INFO"


def test_fhir_latest_fact():
    resources = [{"id": "new", "code": {"coding": [{"code": "4548-4"}]}, "valueQuantity": {"value": 9.1,"unit":"%"},
                  "effectiveDateTime": T0.isoformat(), "method": {"text":"POC"}},
                 {"id": "old", "code": {"coding": [{"code": "4548-4"}]}, "valueQuantity": {"value": 11.2,"unit":"%"},
                  "effectiveDateTime": (T0-timedelta(days=90)).isoformat()}]
    s = PatientSnapshot.from_fhir("opaque", resources)
    assert s.facts["hba1c"].value == 9.1
    assert len(s.history) == 2


def test_molar_conversion_cannot_cross_analytes():
    c = Criterion(id="creat",type="inclusion",field="creatinine",operator="lte",max=2,unit="mg/dL",source_text="Creatinine at most 2 mg/dL.")
    assert evaluate(c,fact("creatinine",0.09,unit="mmol/L"),T0).reason=="UNIT_MISMATCH"
