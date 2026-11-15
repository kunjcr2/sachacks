from datetime import date
from rematch.common.fields import FIELDS
from rematch.common.schemas import Criterion, CriterionResult, FieldFact
from rematch.common.units import normalize


def compare(value, c: Criterion) -> bool:
    if c.operator == "between":
        return c.min <= value <= c.max
    if c.operator == "gte":
        return value >= (c.min if c.min is not None else c.value)
    if c.operator == "gt":
        return value > (c.min if c.min is not None else c.value)
    if c.operator == "lte":
        return value <= (c.max if c.max is not None else c.value)
    if c.operator == "lt":
        return value < (c.max if c.max is not None else c.value)
    if c.operator == "eq":
        return value == c.value
    if c.operator == "in":
        return value in c.value
    if c.operator == "present":
        return value is True or value == 1 or value == "active" or value == "present"
    if c.operator == "absent":
        return value is False or value == 0 or value == "inactive" or value == "absent"
    raise ValueError("Unsupported operator")


def evaluate(c: Criterion, fact: FieldFact | None, today: date) -> CriterionResult:
    registry = FIELDS.get(c.field)
    result = dict(criterion_id=c.id, status="UNKNOWN", reason="MISSING",
                  reuse_class="MISSING", explanation="No authorized clinical fact is available.")
    if not registry:
        return CriterionResult(**(result | {"reason": "UNMAPPED", "explanation": "Manual review: unsupported clinical concept."}))
    if fact is None:
        if c.assessment_stage == "screening_only":
            result.update(reason="SCREENING_ONLY", reuse_class="REPEAT_REQUIRED" if c.central_lab_required else "MISSING",
                          explanation="To be assessed at formal screening; does not block preliminary screening.")
        return CriterionResult(**result)
    age = (today - fact.effective_date).days
    window = c.recency_days if c.recency_days is not None else registry.recency
    result.update(patient_value=fact.value, patient_unit=fact.unit, effective_date=fact.effective_date, age_days=age)
    reuse = "N/A"
    if registry.kind in {"lab", "vital"}:
        reuse = ("REPEAT_REQUIRED" if c.central_lab_required or (window is not None and age > window)
                 else "REUSABLE_AFTER_VERIFICATION" if (fact.method or "").upper() not in {"HPLC", "CENTRAL", "STANDARD"}
                 or (c.fasting_required and fact.fasting is not True) else "REUSABLE")
    result["reuse_class"] = reuse
    if age < 0:
        return CriterionResult(**(result | {"reason": "FUTURE", "explanation": "Future-dated facts cannot be used."}))
    if window is not None and age > window:
        return CriterionResult(**(result | {"reason": "STALE", "explanation": f"Result is {age} days old; protocol window is {window} days."}))
    value = fact.value
    converted = False
    if registry.unit is not None:
        try:
            value, converted = normalize(float(value), fact.unit, c.unit or registry.unit, field=c.field)
        except (ValueError, TypeError):
            return CriterionResult(**(result | {"reason": "UNIT_MISMATCH", "explanation": "Incompatible or missing units; review required."}))
    try:
        condition = compare(value, c)
    except (TypeError, ValueError):
        return CriterionResult(**(result | {"reason": "UNMAPPED", "explanation": "Fact type is incompatible with this rule."}))
    met = condition if c.type == "inclusion" else not condition
    result.update(status="MET" if met else "NOT_MET", reason="OK", normalized_value=value,
                  explanation=("Requirement satisfied." if met else "Requirement not satisfied.") +
                  (" UNIT_CONVERTED to the criterion unit." if converted else ""))
    if c.assessment_stage == "screening_only":
        result["explanation"] += " To be assessed at formal screening; excluded from preliminary decision."
    return CriterionResult(**result)
