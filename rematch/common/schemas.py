from __future__ import annotations

from datetime import date
from typing import Literal
import math
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
    extraction: Literal["curated", "llm", "manual"] = "curated"
    review_status: Literal["draft", "verified"] = "draft"

    @model_validator(mode="after")
    def valid_bounds(self):
        if self.operator == "between" and (self.min is None or self.max is None):
            raise ValueError("between requires min and max")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min must not exceed max")
        if self.operator in {"gte", "gt"} and self.min is None and not isinstance(self.value, (int, float)):
            raise ValueError("Lower-bound comparison needs a number")
        if self.operator in {"lte", "lt"} and self.max is None and not isinstance(self.value, (int, float)):
            raise ValueError("Upper-bound comparison needs a number")
        if self.operator == "in" and not isinstance(self.value, list):
            raise ValueError("in requires a list")
        if self.operator == "eq" and self.value is None:
            raise ValueError("eq requires value")
        return self


class TrialBundle(Model):
    trial_id: str
    version: int = Field(ge=1)
    title: str
    plain_language_summary: str
    sponsor_id: str = "meridian"
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
            raise ValueError("Criterion IDs must be unique")
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


class AggregateSignal(Model):
    clinic_id: str
    trial_id: str
    trial_version: int
    evaluated: int | None = Field(ge=0)
    potential: int | None = Field(ge=0)
    needs_info: int | None = Field(ge=0)
    not_matched: int | None = Field(ge=0)
    new_this_period: int | None = Field(ge=0)
    min_cell_size: int = Field(default=1, ge=1, le=100)
    suppressed: bool = False


class CandidateEvidence(Model):
    criterion_id: str
    field: str
    value: str | float | bool | None
    unit: str | None
    days_before_packet: int | None = Field(ge=0)
    status: Literal["MET", "NOT_MET", "UNKNOWN"]
    reuse_class: str


class RematchEvidence(Model):
    trigger: Literal["LAB_UPDATE", "TRIAL_UPDATE", "CLOCK", "CONSENT", "SYNC"]
    days_before_packet: int = Field(ge=0)
    before_status: str
    after_status: str


class CandidatePacket(Model):
    ref: str = Field(pattern=r"^RM-[A-Z2-7]{10}$")
    trial_id: str
    trial_version: int
    age_band: str | None = None
    sex: Literal["female", "male", "other", "unknown"] | None = None
    evidence: list[CandidateEvidence]
    rematch: bool = False
    rematch_history: list[RematchEvidence] = Field(default_factory=list)


class SealedReferral(Model):
    referral_id: str
    clinic_id: str
    trial_id: str
    key_id: str
    ciphertext_b64: str
    created_at: date


class SponsorResponse(Model):
    referral_id: str
    decision: Literal["confirm", "needs_data", "decline"]
    requested_criteria_ids: list[str] = Field(default_factory=list)
    note: str = Field(default="", max_length=240)


class ConsentUpdate(Model):
    broad_status: Literal["NOT_ASKED", "OPTED_IN", "DECLINED", "WITHDRAWN"]
    contact_pref: Literal["email", "phone", "clinic portal"] = "clinic portal"


class Decision(Model):
    action: Literal["approve", "hold", "dismiss"]
    note: str = Field(default="", max_length=500)


class PatientResponse(Model):
    response: Literal["interested", "later", "no"]


class ClockAdvance(Model):
    days: int = Field(ge=0, le=365)


class SponsorRegistration(Model):
    sponsor_id: str
    name: str
    public_key_b64: str


class ClinicRegistration(Model):
    clinic_id: str
    name: str
