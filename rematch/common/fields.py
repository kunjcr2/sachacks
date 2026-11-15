from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    kind: str
    unit: str | None = None
    mutable: bool = True
    recency: int | None = None
    code: str | None = None


FIELDS = {
    "age": Field("demographic", "years", False),
    "sex": Field("demographic", None, False),
    "hba1c": Field("lab", "%", True, 90, "4548-4"),
    "egfr": Field("lab", "mL/min/1.73m2", True, 180, "62238-1"),
    "creatinine": Field("lab", "mg/dL", True, 180, "2160-0"),
    "alt": Field("lab", "U/L", True, 180, "1742-6"),
    "bmi": Field("vital", "kg/m2", True, 90, "39156-5"),
    "sbp": Field("vital", "mmHg", True, 30, "8480-6"),
    "dbp": Field("vital", "mmHg", True, 30, "8462-4"),
    "cpeptide": Field("lab", "ng/mL"),
    **{f"dx_{x}": Field("condition", None, False) for x in ["t2dm", "ckd", "htn", "hf"]},
    "pregnant": Field("condition", None, True, 30),
    **{f"rx_{x}": Field("medication", None, x != "insulin") for x in ["metformin", "insulin", "sglt2i", "glp1ra"]},
}
# Insulin use is a non-watch blocker in the scripted demonstration; therapy changes
# require clinician judgment and are never suggested to obtain research access.
CODE_FIELDS = {v.code: k for k, v in FIELDS.items() if v.code}
CODE_FIELDS.update({"44054006": "dx_t2dm", "709044004": "dx_ckd", "38341003": "dx_htn",
                    "84114007": "dx_hf", "77386006": "pregnant"})
