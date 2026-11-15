from datetime import date
from rematch.common.fields import FIELDS
from rematch.common.schemas import MatchResult, TrialBundle
from .evaluators import evaluate
from .snapshot import PatientSnapshot


def match(snapshot: PatientSnapshot, trial: TrialBundle, today: date) -> MatchResult:
    results = [evaluate(c, snapshot.facts.get(c.field), today) for c in trial.criteria]
    preliminary = [(c, r) for c, r in zip(trial.criteria, results) if c.assessment_stage == "preliminary"]
    blockers = [c.id for c, r in preliminary if r.status == "NOT_MET"]
    # An empty preliminary protocol cannot establish a potential match.
    status = "NOT_MATCHED" if blockers else "NEEDS_INFO" if not preliminary or any(r.status == "UNKNOWN" for _, r in preliminary) else "POTENTIAL_MATCH"
    watch = bool(blockers) and all(FIELDS[c.field].mutable for c, r in preliminary if r.status == "NOT_MET")
    return MatchResult(patient_id=snapshot.patient_id, trial_id=trial.trial_id, trial_version=trial.version,
                       as_of=today, status=status, criteria=results, blocking_criteria=blockers, watch=watch)
