import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rematch.common.clock import T0
from rematch.common.config import ROOT
from rematch.common.schemas import Criterion, TrialBundle


def build_trials():
    definitions = [
        ("SYN-0001", "ReNew-T2D-01", "A fictional study of an additional treatment for type 2 diabetes.", [
            ("age", "between", 40, 70, "years", "Age 40 to 70 years.", "inclusion"),
            ("dx_t2dm", "present", None, None, None, "Type 2 diabetes is required.", "inclusion"),
            ("hba1c", "between", 7.5, 10, "%", "HbA1c must be between 7.5% and 10%.", "inclusion"),
            ("egfr", "gte", 45, None, "mL/min/1.73m2", "eGFR at least 45 mL/min/1.73m2.", "inclusion"),
            ("bmi", "between", 25, 40, "kg/m2", "BMI 25 to 40 kg/m2.", "inclusion"),
            ("rx_metformin", "present", None, None, None, "Active metformin treatment is required.", "inclusion"),
            ("rx_insulin", "present", None, None, None, "Current insulin use is excluded.", "exclusion"),
            ("pregnant", "present", None, None, None, "Current pregnancy is excluded.", "exclusion"),
            ("cpeptide", "gte", 0.5, None, "ng/mL", "C-peptide at least 0.5 ng/mL at central-lab screening.", "inclusion")]),
        ("SYN-0002", "Kidney Forward", "A fictional kidney-health research study.", [
            ("age", "between", 35, 80, "years", "Age 35 to 80 years.", "inclusion"),
            ("dx_ckd", "present", None, None, None, "Chronic kidney disease is required.", "inclusion"),
            ("egfr", "between", 30, 60, "mL/min/1.73m2", "eGFR 30 to 60 mL/min/1.73m2.", "inclusion")]),
        ("SYN-0003", "Pressure Pathways", "A fictional study of support for high blood pressure.", [
            ("age", "between", 30, 75, "years", "Age 30 to 75 years.", "inclusion"),
            ("dx_htn", "present", None, None, None, "Hypertension is required.", "inclusion"),
            ("sbp", "between", 140, 180, "mmHg", "Systolic blood pressure 140 to 180 mmHg.", "inclusion")]),
        ("SYN-0004", "Metabolic Horizons", "A fictional study of metabolic health.", [
            ("age", "between", 40, 70, "years", "Age 40 to 70 years.", "inclusion"),
            ("hba1c", "between", 8, 9.5, "%", "HbA1c 8% to 9.5%.", "inclusion"),
            ("bmi", "between", 27, 40, "kg/m2", "BMI 27 to 40 kg/m2.", "inclusion")]),
        ("SYN-0005", "Everyday Balance", "A fictional study of a supported nutrition program.", [
            ("age", "between", 18, 75, "years", "Age 18 to 75 years.", "inclusion"),
            ("bmi", "between", 30, 45, "kg/m2", "BMI 30 to 45 kg/m2.", "inclusion")]),
    ]
    bundles = []
    for tid, title, summary, rules in definitions:
        criteria = []
        for i, (field, op, low, high, unit, source, kind) in enumerate(rules, 1):
            criteria.append(Criterion(id=f"{tid}-C{i}", type=kind, field=field, operator=op, min=low, max=high,
                                       unit=unit, source_text=source, 
                                       assessment_stage="screening_only" if field == "cpeptide" else "preliminary",
                                       central_lab_required=field == "cpeptide"))
        bundles.append(TrialBundle(trial_id=tid, version=1, title=title, plain_language_summary=summary,
                                   source_ref=f"Synthetic protocol {tid}", last_updated=T0,
                                   raw_eligibility_text="\n".join(c.source_text for c in criteria), criteria=criteria,
                                   visits_summary="Demo only: an initial screening visit and monthly follow-up visits for three months."))
    return bundles
