"""Optional public-text-only OpenAI adapter. Never imported by the matcher."""
import hashlib
import json
import os
import re
from pydantic import Field
from rematch.common.config import ROOT
from rematch.common.schemas import Model,Criterion
from rematch.common.fields import FIELDS
from .validate import validate_criteria

PROMPT_VERSION = "public-rules-v1"


class ExtractedCriteria(Model):
    criteria:list[Criterion] = Field(min_length=1)


def cache_key(text,model):
    return hashlib.sha256((PROMPT_VERSION+"\0"+model+"\0"+text).encode()).hexdigest()


class LLMExtractor:
    def __init__(self,client=None,model=None,cache_dir=None):
        self.model = model or os.getenv("OPENAI_MODEL")
        if not self.model:
            raise ValueError("Set OPENAI_MODEL in .env to a model supporting Structured Outputs. The offline demo does not require it.")
        if client is None:
            from openai import OpenAI
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError("Set OPENAI_API_KEY locally in .env. Only public trial criteria are sent.")
            client = OpenAI(timeout=45,max_retries=1)
        self.client = client
        self.cache_dir = cache_dir or ROOT/"data/trials/cache"

    def extract(self,trial_id,eligibility_text):
        self.cache_dir.mkdir(parents=True,exist_ok=True)
        path = self.cache_dir/f"{cache_key(eligibility_text,self.model)}.json"
        if path.exists():
            draft = ExtractedCriteria.model_validate_json(path.read_text())
        else:
            response = self.client.responses.parse(model=self.model,temperature=0,store=False,
                instructions=("Extract explicit rules from PUBLIC clinical-trial criteria. Never decide patient eligibility. "
                "Copy source_text verbatim. Preserve inclusion/exclusion polarity, numeric bounds and units. "
                "Do not discard requirements. Each ambiguous or unsupported clause, including compound AND/OR logic, "
                "exceptions, and treatment windows, must be an unmapped draft requiring human review. "
                "All review_status values must be draft. Canonical fields: "+", ".join(FIELDS)),
                input=eligibility_text,text_format=ExtractedCriteria)
            draft = response.output_parsed
            if draft is None:
                raise ValueError("No structured extraction returned; use the curated demo or review manually.")
            path.write_text(draft.model_dump_json(indent=2))
        criteria = []
        for i,c in enumerate(draft.criteria,1):
            c = c.model_copy(update={"id":f"{trial_id}-C{i}","extraction":"llm","review_status":"draft"})
            if c.field not in FIELDS:
                c.field = "unmapped"
            # Flat rules cannot safely express compound logic. Preserve the quote.
            text = re.sub(r"between\s+[\d.]+\s*%?\s+and\s+[\d.]+","range",c.source_text,flags=re.I)
            if re.search(r"\b(and|or|unless|except|prior|within|either)\b",text,re.I):
                c.field = "unmapped"
            criteria.append(c)
        return validate_criteria(criteria,eligibility_text)
