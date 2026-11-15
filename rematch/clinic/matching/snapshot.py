from dataclasses import dataclass, field
from datetime import date
from rematch.common.fields import CODE_FIELDS, FIELDS
from rematch.common.schemas import FieldFact


@dataclass
class PatientSnapshot:
    patient_id: str
    facts: dict[str, FieldFact] = field(default_factory=dict)
    history: list[FieldFact] = field(default_factory=list)

    @classmethod
    def from_facts(cls, patient_id: str, facts: list[FieldFact]):
        latest = {}
        for fact in facts:
            if fact.field not in latest or fact.effective_date >= latest[fact.field].effective_date:
                latest[fact.field] = fact
        return cls(patient_id, latest, facts)

    @classmethod
    def from_fhir(cls, patient_id: str, resources: list[dict]):
        facts = []
        for resource in resources:
            code = resource.get("code", {}).get("coding", [{}])[0].get("code")
            key = CODE_FIELDS.get(code, code if code in FIELDS else None)
            if key is None:
                continue
            quantity = resource.get("valueQuantity")
            value = quantity["value"] if quantity else resource.get("valueBoolean")
            if value is None:
                continue
            facts.append(FieldFact(field=key, value=value, unit=quantity["unit"] if quantity else None,
                                   effective_date=date.fromisoformat(resource["effectiveDateTime"][:10]),
                                   method=(resource.get("method") or {}).get("text"),
                                   source_resource_id=resource["id"]))
        return cls.from_facts(patient_id, facts)
