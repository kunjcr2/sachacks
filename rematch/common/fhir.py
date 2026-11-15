from typing import Literal
from datetime import datetime
from pydantic import Field
from .schemas import Model


class Coding(Model):
    system: str = "http://loinc.org"
    code: str
    display: str | None = None


class CodeableConcept(Model):
    coding: list[Coding]


class Reference(Model):
    reference: str


class Quantity(Model):
    value: float
    unit: str


class Method(Model):
    text: str


class Observation(Model):
    resourceType: Literal["Observation"] = "Observation"
    id: str
    status: Literal["final", "amended", "corrected"] = "final"
    code: CodeableConcept
    subject: Reference
    effectiveDateTime: datetime
    valueQuantity: Quantity
    method: Method | None = None


class ClinicalResource(Model):
    resourceType: Literal["Condition", "MedicationStatement"]
    id: str
    subject: Reference
    code: CodeableConcept
    effectiveDateTime: datetime
    valueBoolean: bool


class BundleEntry(Model):
    resource: Observation | ClinicalResource


class Bundle(Model):
    resourceType: Literal["Bundle"] = "Bundle"
    type: Literal["collection"] = "collection"
    entry: list[BundleEntry] = Field(min_length=1, max_length=200)
