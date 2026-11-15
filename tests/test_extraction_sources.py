from types import SimpleNamespace
import pytest
from rematch.common.schemas import Criterion,TrialBundle
from rematch.extraction.curated import CuratedExtractor,load_trials
from rematch.extraction.validate import validate_criteria
from rematch.extraction.llm import LLMExtractor,ExtractedCriteria,cache_key
from rematch.extraction.ctgov import cached_trials,trial_preview


def test_curated_source_fidelity_and_version_gate():
    for trial in load_trials():
        criteria = CuratedExtractor().extract(trial.trial_id,trial.raw_eligibility_text)
        assert validate_criteria(criteria,trial.raw_eligibility_text,publication=True)
        with pytest.raises(ValueError):
            CuratedExtractor().extract(trial.trial_id,trial.raw_eligibility_text+" amended")
    c = trial.criteria[0].model_copy(update={"source_text":"This quotation is invented"})
    with pytest.raises(ValueError,match="verbatim"):
        validate_criteria([c],trial.raw_eligibility_text)


def test_ambiguous_logic_and_drafts_rejected():
    c = Criterion(id="c",type="inclusion",field="dx_t2dm",operator="present",source_text="Diabetes or chronic kidney disease.",review_status="verified")
    with pytest.raises(ValueError,match="compound"):
        validate_criteria([c],c.source_text,publication=True)
    c.field = "unmapped"
    assert validate_criteria([c],c.source_text,publication=True)
    c.review_status = "draft"
    with pytest.raises(ValueError,match="verification"):
        validate_criteria([c],c.source_text,publication=True)


def test_optional_llm_adapter_public_text_cache_and_draft_only(tmp_path):
    calls = []
    quote = "HbA1c must be between 7.5% and 10%."
    criterion = load_trials()[0].criteria[2]
    def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(output_parsed=ExtractedCriteria(criteria=[criterion]))
    fake = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    extractor = LLMExtractor(fake,"test-model",tmp_path)
    output = extractor.extract("NCT00000000",quote)
    assert output[0].review_status=="draft" and output[0].extraction=="llm"
    assert calls[0]["input"]==quote and calls[0]["store"] is False
    extractor.extract("NCT00000000",quote)
    assert len(calls)==1
    assert cache_key(quote,"a")!=cache_key(quote,"b")
    assert cache_key(quote,"a")!=cache_key(quote+" change","a")


def test_real_public_cache_retains_exact_source():
    sources = cached_trials()
    assert sources,"At least one actual public API record must ship with the offline demo"
    for cached in sources:
        preview = trial_preview(cached)
        assert preview["eligibility"]==cached["record"]["protocolSection"]["eligibilityModule"]["eligibilityCriteria"]
        assert preview["nct_id"].startswith("NCT")
