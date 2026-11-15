from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from rematch.common.schemas import GeneratedStudy, ModelReview
from rematch.extraction.ctgov import cached_trials, trial_preview
from rematch.extraction.sources import synthetic_source, public_source, fingerprint
from rematch.extraction.validate import validate_generated, supported_risk
from rematch.extraction.llm import LLMExtractor, cache_key
from rematch.seed import offline_spec
from rematch.service import RuleError
from tests.conftest import connect

def fixture():
    source = synthetic_source('SYN-LOW')
    return source, GeneratedStudy.model_validate(offline_spec(source)['generated'])

@pytest.mark.parametrize('change', ['quote', 'bounds', 'operator', 'field', 'unit', 'polarity', 'logic', 'missing', 'duplicate', 'modifier', 'location'])
def test_bad_rules_never_publish(service, change):
    source, generated = fixture()
    c = generated.criteria[0]
    if change == 'quote':
        c.source_text = 'Invented age criterion'
    elif change == 'bounds':
        c.min = 75
    elif change == 'operator':
        c.operator = 'gte'
    elif change == 'field':
        c.field = 'bmi'
    elif change == 'unit':
        c.unit = '%'
    elif change == 'polarity':
        c.type = 'exclusion'
    elif change == 'logic':
        source['eligibility'] = 'Age between 18 and 75 years or diabetes.'
        c.source_text = source['eligibility']
    elif change == 'missing':
        source['eligibility'] += '\nInsulin use is excluded.'
    elif change == 'duplicate':
        generated.criteria.append(c.model_copy())
    elif change == 'modifier':
        c.assessment_stage = 'screening_only'
    else:
        c.source_location = 'invented'
    errors = validate_generated(generated, source)
    assert errors
    spec = offline_spec(synthetic_source('SYN-LOW'))
    spec['generated'] = generated.model_dump(mode='json')
    spec['source_hash'] = source['hash']
    with pytest.raises(RuleError):
        service.publish(source, spec, 'team-1')

def test_unsupported_and_missing_coverage_cannot_disappear(service):
    source, generated = fixture()
    generated.unmapped = ['Unclear treatment history']
    assert any('Unmapped' in x for x in validate_generated(generated, source))
    generated.criteria[0].field = 'unmapped'
    assert any('unsupported field' in x for x in validate_generated(generated, source))

@pytest.mark.parametrize('scenario', ['no_evidence', 'wrong_quote', 'wrong_location', 'conflicting', 'unsupported_inference', 'negation'])
def test_unsupported_low_risk_falls_back_to_doctor(service, scenario):
    source, generated = fixture()
    if scenario == 'no_evidence':
        generated.risk_evidence = None
    elif scenario == 'wrong_quote':
        generated.risk_evidence.quote = 'Fabricated low risk'
    elif scenario == 'wrong_location':
        generated.risk_evidence.location = 'missing'
    else:
        text = {'conflicting': 'Low risk or high risk is uncertain.', 'unsupported_inference': 'This is an observational study.', 'negation': 'This is not low risk.'}[scenario]
        source['documents']['synthetic:route'] = text
        generated.risk_evidence.location = 'synthetic:route'
        generated.risk_evidence.quote = text
    assert supported_risk(generated, source) == 'UNKNOWN'
    spec = offline_spec(synthetic_source('SYN-LOW'))
    spec['generated'] = generated.model_dump(mode='json')
    row = service.publish(source, spec, 'team-1')
    assert row['risk'] == 'UNKNOWN'
    connect(service)
    assert service.store.get('discussion', 'patient-1|SYN-LOW:team-1')['outcome'] == 'PENDING'
    with pytest.raises(RuleError):
        service.preview('patient-1', 'SYN-LOW:team-1')

def test_brief_quotes_and_missing_facts(service):
    source = synthetic_source('SYN-UNKNOWN')
    row = service.publish(source, offline_spec(source), 'team-2')
    brief = service.brief(row)
    assert len(brief) == 5
    assert brief[2]['text'] == 'Not provided in the available study information.'
    assert brief[4]['text'] == 'Not provided in the available study information.'
    assert 'No individual benefit is guaranteed.' in brief[3]['text']
    generated = GeneratedStudy.model_validate(row['specification']['generated'])
    generated.purpose.quote = 'An invented promised cure'
    assert validate_generated(generated, source)

def test_live_generation_model_review_and_source_only_cache(tmp_path):
    source, generated = fixture()
    calls = []
    def parse(**kwargs):
        calls.append(kwargs)
        parsed = generated if kwargs['text_format'] is GeneratedStudy else ModelReview(consistent=True, errors=[])
        return SimpleNamespace(output_parsed=parsed)
    extractor = LLMExtractor(SimpleNamespace(responses=SimpleNamespace(parse=parse)), 'test-model', tmp_path)
    source['patient_name'] = 'DO NOT SEND'
    source['clinical_records'] = {'hba1c': 9.1}
    result = extractor.generate(source)
    assert result['state'] == 'VALIDATED_FOR_DEMO' and result['execution'] == 'live_model'
    assert len(calls) == 2 and all(c['store'] is False for c in calls)
    assert 'DO NOT SEND' not in json.dumps(calls, default=str)
    assert 'clinical_records' not in json.dumps(calls, default=str)
    assert result['generated']['criteria'][0]['extraction'] == 'llm'
    again = extractor.generate(source)
    assert again['execution'] == 'validated_model_cache' and len(calls) == 2
    assert cache_key(source, 'a') != cache_key(source, 'b')
    revised = deepcopy(source)
    revised['hash'] = 'changed'
    assert cache_key(source, 'a') != cache_key(revised, 'a')

def test_model_review_blocks_and_does_not_cache(tmp_path):
    source, generated = fixture()
    def parse(**kwargs):
        return SimpleNamespace(output_parsed=generated if kwargs['text_format'] is GeneratedStudy else ModelReview(consistent=False, errors=['Incomplete polarity review']))
    extractor = LLMExtractor(SimpleNamespace(responses=SimpleNamespace(parse=parse)), 'test-model', tmp_path)
    result = extractor.generate(source)
    assert result['state'] == 'BLOCKED'
    assert not list(tmp_path.glob('*.json'))

def test_api_model_failure_preserves_existing_valid_listing(api, service, monkeypatch):
    before = service.store.get('listing', 'SYN-LOW:team-1')
    def fail(*args, **kwargs):
        raise RuntimeError('Sensitive SDK error should never be returned')
    monkeypatch.setattr(LLMExtractor, 'generate', fail)
    response = api('team-1', 'POST', '/team/listings', {'source_id': 'SYN-LOW', 'mode': 'live'})
    assert response.status_code == 502 and 'Sensitive SDK' not in response.text
    assert service.store.get('listing', 'SYN-LOW:team-1') == before

def test_source_fidelity_retains_completed_public_cache():
    cached = cached_trials()
    assert cached
    view = trial_preview(cached[0])
    assert view['eligibility'] == cached[0]['record']['protocolSection']['eligibilityModule']['eligibilityCriteria']
    source = public_source('NCT03548935')
    assert source['status'] == 'closed'
    assert view['eligibility'] in source['documents']['registry:eligibility']
    assert source['hash'] == fingerprint(source)

def test_live_offline_statuses_never_confused(api):
    result = api('team-1', 'POST', '/team/listings', {'source_id': 'SYN-LOW', 'mode': 'offline'}).json()
    assert result['execution'] == 'offline_synthetic_fixture'
