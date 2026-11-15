from typing import Protocol
from rematch.common.schemas import Criterion


class CriteriaExtractor(Protocol):
    def extract(self, trial_id: str, eligibility_text: str) -> list[Criterion]: ...
