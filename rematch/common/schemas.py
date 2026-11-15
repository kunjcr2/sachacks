from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

class Criterion(Model):
    id: str = Field(min_length=1, max_length=100)
    type: Literal["inclusion", "exclusion"]
    field: str
    operator: Literal["between", "gte", "lte", "gt", "lt", "eq", "in", "present", "absent"]
    min: float | None = None
    max: float | None = None
    value: str | float | bool | list[str] | None = None
    unit: str | None = None
    recency_days: int | None = Field(default=None, ge=0)
    central_lab_required: bool = False
    fasting_required: bool = False
    assessment_stage: Literal["preliminary", "screening_only"] = "preliminary"
    source_text: str = Field(min_length=1)
    source_location: str = "registry:eligibility"
    extraction: Literal["synthetic_fixture", "llm"] = "synthetic_fixture"

    @model_validator(mode="after")
    def bounds(self):
        if self.operator == "between" and (self.min is None or self.max is None or self.min > self.max):
            raise ValueError("between requires ordered bounds")
        if self.operator in {"gte", "gt"} and self.min is None and not isinstance(self.value, (int, float)):
            raise ValueError("Lower bound required")
        if self.operator in {"lte", "lt"} and self.max is None and not isinstance(self.value, (int, float)):
            raise ValueError("Upper bound required")
        if self.operator == "eq" and self.value is None:
            raise ValueError("eq requires a value")
        if self.operator == "in" and not isinstance(self.value, list):
            raise ValueError("in requires a list")
        return self

class TrialBundle(Model):
    trial_id: str
    version: int = Field(ge=1)
    title: str
    plain_language_summary: str
    registry_sponsor: str | None = None
    source: Literal["synthetic", "clinicaltrials.gov"] = "synthetic"
    source_ref: str
    status: Literal["recruiting", "paused", "closed"] = "recruiting"
    last_updated: date
    raw_eligibility_text: str
    criteria: list[Criterion] = Field(min_length=1)
    visits_summary: str

    @model_validator(mode="after")
    def unique_ids(self):
        if len({c.id for c in self.criteria}) != len(self.criteria):
            raise ValueError("Duplicate criterion IDs")
        return self

class FieldFact(Model):
    field: str
    value: str | float | bool
    unit: str | None = None
    effective_date: date
    method: str | None = None
    fasting: bool | None = None
    source_resource_id: str

class CriterionResult(Model):
    criterion_id: str
    status: Literal["MET", "NOT_MET", "UNKNOWN"]
    reason: str
    patient_value: str | float | bool | None = None
    patient_unit: str | None = None
    normalized_value: str | float | bool | None = None
    effective_date: date | None = None
    age_days: int | None = None
    reuse_class: Literal["REUSABLE", "REUSABLE_AFTER_VERIFICATION", "REPEAT_REQUIRED", "MISSING", "N/A"]
    explanation: str

class MatchResult(Model):
    patient_id: str
    trial_id: str
    trial_version: int
    as_of: date
    status: Literal["POTENTIAL_MATCH", "NEEDS_INFO", "NOT_MATCHED"]
    criteria: list[CriterionResult]
    blocking_criteria: list[str]
    watch: bool

class Identity(Model):
    name: str = Field(min_length=1, max_length=100)
    contact_method: Literal["email", "phone"]
    contact: str = Field(min_length=1, max_length=150)

class Onboard(Identity):
    assigned_pcp: Literal["doctor-1"] | None = "doctor-1"

class PermissionUpdate(Model):
    kind: Literal["screening", "records"]
    granted: bool

class DiscussionUpdate(Model):
    outcome: Literal["COMPLETED", "NEED_INFO", "DEFERRED"]
    note: str = Field(default="", max_length=500)

class IntroductionAuthorization(Model):
    preview_id: str
    confirmed: bool

class Followup(Model):
    action: Literal["ACKNOWLEDGED", "NEED_INFO", "SCREENING_INVITED", "CLOSED", "ENROLLED"]

class BriefClaim(Model):
    quote: str
    location: str

class GeneratedStudy(Model):
    criteria: list[Criterion] = Field(min_length=1)
    purpose: BriefClaim | None
    participation: BriefClaim | None
    risks: BriefClaim | None
    benefits: BriefClaim | None
    compensation: BriefClaim | None
    importance: BriefClaim | None
    risk_route: Literal["LOW", "HIGH", "UNKNOWN"]
    risk_evidence: BriefClaim | None
    unmapped: list[str]

class ModelReview(Model):
    consistent: bool
    errors: list[str]

class ListingRequest(Model):
    source_id: str
    mode: Literal["offline", "live"] = "offline"

class ClockAdvance(Model):
    days: int = Field(ge=0, le=365)

class DemoSession(Model):
    actor: str = Field(min_length=1, max_length=100)
