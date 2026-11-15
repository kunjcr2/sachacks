import json
import pytest
from cryptography.exceptions import InvalidTag
from rematch.common.crypto import Vault
from rematch.extraction.sources import synthetic_source, fingerprint
from rematch.seed import offline_spec, seed
from rematch.service import RuleError
from tests.conftest import connect

LOW = 'SYN-LOW:team-1'
HIGH = 'SYN-HIGH:team-1'
UNKNOWN = 'SYN-UNKNOWN:team-1'
REMATCH = 'SYN-REMATCH:team-1'

def authorize(service, listing=LOW, pid='patient-1'):
    preview = service.preview(pid, listing)
    result = service.authorize(pid, preview['id'], True)
    return preview, result

def test_self_onboarding_no_invitation_and_declining_preserves_credit(api, service):
    response = api('onboarding', 'POST', '/profiles', dict(name='New Synthetic', contact_method='email', contact='new@example.invalid', assigned_pcp=None))
    assert response.status_code == 200
    pid = response.json()['patient_id']
    assert response.json()['demo_token']
    assert not service.permitted(pid, 'screening')
    assert service.profile(pid)['opportunities'] == []
    credit = service.store.get('payment', pid)
    service.permission(pid, 'screening', False)
    service.permission(pid, 'records', False)
    assert service.store.get('payment', pid) == credit
    with pytest.raises(RuleError):
        service.import_records(pid)

@pytest.mark.parametrize('screening,records', [(False, False), (True, False), (False, True)])
def test_import_permission_boundaries(service, screening, records):
    service.permission('patient-1', 'screening', screening)
    service.permission('patient-1', 'records', records)
    with pytest.raises(RuleError):
        service.import_records('patient-1')
    assert service.store.all('clinical') == []

def test_low_direct_high_and_unknown_discussion_queue(api, service):
    connect(service)
    profile = api('patient-1', 'GET', '/me').json()
    low = next(x for x in profile['opportunities'] if x['listing_id'] == LOW)
    assert low['status'] == 'POTENTIAL_MATCH' and not low['waiting_for_doctor']
    assert [line['heading'] for line in low['study']['brief']] == ['Purpose', 'What participation involves', 'Main risks and uncertainties', 'Possible benefits', 'Costs and compensation']
    queue = api('doctor-1', 'GET', '/doctor/discussions').json()
    assert {x['listing_id'] for x in queue} == {HIGH, UNKNOWN}
    assert not any(x['listing_id'] == LOW for x in service.store.all('discussion'))
    for listing in [HIGH, UNKNOWN]:
        pending = next(x for x in profile['opportunities'] if x['listing_id'] == listing)
        assert pending['waiting_for_doctor'] and 'study' not in pending
        assert api('patient-1', 'POST', '/me/studies/' + listing + '/preview').status_code == 409
    assert api('team-1', 'GET', '/team/introductions').json() == []
    assert api('team-1', 'GET', '/patients').status_code == 404

def test_higher_risk_discussion_and_missing_pcp_cannot_bypass(service):
    connect(service)
    service.discuss('doctor-1', 'patient-1|' + HIGH, 'NEED_INFO', 'Review next visit')
    with pytest.raises(RuleError):
        service.preview('patient-1', HIGH)
    service.discuss('doctor-1', 'patient-1|' + HIGH, 'COMPLETED', 'Voluntary discussion')
    assert service.preview('patient-1', HIGH)['recipient']['site']
    connect(service, 'patient-2')
    with pytest.raises(RuleError):
        service.preview('patient-2', HIGH)
    with pytest.raises(RuleError):
        service.discuss('doctor-1', 'patient-2|' + HIGH, 'COMPLETED', '')
    waiting = next(x for x in service.profile('patient-2')['opportunities'] if x['listing_id'] == HIGH)
    assert 'no doctor is assigned' in waiting['message']

def test_principal_and_role_checks(api, service):
    assert api('invalid', 'GET', '/me').status_code == 401
    assert api('team-1', 'GET', '/me').status_code == 403
    assert api('patient-1', 'GET', '/doctor/discussions').status_code == 403
    assert api('doctor-1', 'GET', '/team/introductions').status_code == 403
    assert api('patient-1', 'POST', '/demo/clock', {'days': 91}).status_code == 403
    assert api('patient-1', 'GET', '/patients/patient-2').status_code == 404
    assert api('patient-1', 'POST', '/me/permissions', {'kind': 'screening', 'granted': True, 'patient_id': 'patient-2'}).status_code == 422
    assert not service.permitted('patient-2', 'screening')

def test_exact_scoped_packet_explicit_authorization_and_idempotency(api, service):
    connect(service)
    preview = api('patient-1', 'POST', '/me/studies/' + LOW + '/preview').json()
    assert service.team_introductions('team-1') == []
    for actor, confirmed in [('patient-2', True), ('patient-1', False)]:
        assert api(actor, 'POST', '/me/introductions', {'preview_id': preview['id'], 'confirmed': confirmed}).status_code == 409
    body = {'preview_id': preview['id'], 'confirmed': True}
    first = api('patient-1', 'POST', '/me/introductions', body)
    assert first.status_code == 200
    assert api('patient-1', 'POST', '/me/introductions', body).json() == first.json()
    intros = service.team_introductions('team-1')
    assert len(intros) == 1 and intros[0]['approved_packet'] == preview['exact_packet']
    assert set(intros[0]['approved_packet']) == {'name', 'preferred_contact', 'screening_summary'}
    assert intros[0]['enrollment'] == 'NOT_REPORTED'
    assert service.team_introductions('team-2') == []
    assert api('team-2', 'POST', '/team/introductions/' + first.json()['id'], {'action': 'ACKNOWLEDGED'}).status_code == 409
    assert len(service.store.all('outbox')) == 1
    assert len(service.store.all('introduction')) == 1
    assert api('patient-2', 'POST', '/me/introductions/' + first.json()['id'] + '/withdraw').status_code == 409

def test_followup_separate_enrollment_and_no_doctor_payment(service):
    connect(service)
    _, intro = authorize(service)
    key = intro['id']
    with pytest.raises(RuleError):
        service.followup('team-1', key, 'ENROLLED')
    service.followup('team-1', key, 'ACKNOWLEDGED')
    assert service.team_introductions('team-1')[0]['enrollment'] == 'NOT_REPORTED'
    service.followup('team-1', key, 'NEED_INFO')
    service.followup('team-1', key, 'SCREENING_INVITED')
    result = service.followup('team-1', key, 'ENROLLED')
    assert result['enrollment'] == 'SIMULATED_ENROLLED'
    assert {x['type'] for x in service.store.all('payment')} == {'listing_fee', 'onboarding_time_credit'}

def test_reassessment_is_idempotent_and_new_records_invalidate_preview(service):
    connect(service)
    count = len(service.store.all('discussion'))
    service.discuss('doctor-1', 'patient-1|' + HIGH, 'COMPLETED', '')
    preview = service.preview('patient-1', HIGH)
    for _ in range(3):
        service.reassess('patient-1')
    assert len(service.store.all('discussion')) == count
    assert service.preview('patient-1', HIGH)
    service.import_records('patient-1', followup=True)
    with pytest.raises(RuleError):
        service.authorize('patient-1', preview['id'], True)
    assert service.store.get('discussion', 'patient-1|' + HIGH)['outcome'] == 'PENDING'
    assert len(service.store.all('discussion')) == count
    profile = service.profile('patient-1')
    assert next(x for x in profile['opportunities'] if x['listing_id'] == REMATCH)['status'] == 'POTENTIAL_MATCH'

def test_clock_staleness_keeps_unknown_and_invalidates_actions(service):
    connect(service)
    service.import_records('patient-1', followup=True)
    preview = service.preview('patient-1', REMATCH)
    service.advance(91)
    item = next(x for x in service.profile('patient-1')['opportunities'] if x['listing_id'] == REMATCH)
    assert item['status'] == 'NEEDS_INFO'
    assert any(c['reason'] == 'STALE' for c in item['reasons'])
    with pytest.raises(RuleError):
        service.authorize('patient-1', preview['id'], True)

def test_changed_source_pauses_actions_before_regeneration_and_closed_study(service):
    connect(service)
    preview, intro = authorize(service)
    source = synthetic_source('SYN-LOW')
    source['status'] = 'closed'
    source['hash'] = fingerprint(source)
    service.update_source(source, 'team-1')
    assert service.store.get('listing', LOW)['status'] == 'paused'
    with pytest.raises(RuleError):
        service.authorize('patient-1', preview['id'], True)
    with pytest.raises(RuleError):
        service.followup('team-1', intro['id'], 'ACKNOWLEDGED')
    row = service.publish(source, offline_spec(source), 'team-1')
    assert row['version'] == 2 and row['status'] == 'closed'
    assert not any(x['listing_id'] == LOW for x in service.profile('patient-1')['opportunities'])
    with pytest.raises(RuleError):
        service.preview('patient-1', LOW)

def test_study_and_risk_revision_require_new_discussion_and_authorization(service):
    connect(service)
    preview = service.preview('patient-1', LOW)
    source = synthetic_source('SYN-LOW')
    spec = offline_spec(source)
    spec['generated']['risk_route'] = 'UNKNOWN'
    row = service.publish(source, spec, 'team-1')
    assert row['version'] == 2 and row['risk'] == 'UNKNOWN'
    with pytest.raises(RuleError):
        service.authorize('patient-1', preview['id'], True)
    assert service.store.get('discussion', 'patient-1|' + LOW)['outcome'] == 'PENDING'

def test_disconnect_retains_authorized_records_but_blocks_import(service):
    connect(service)
    service.permission('patient-1', 'records', False)
    assert service.resources('patient-1')
    assert service.profile('patient-1')['opportunities']
    with pytest.raises(RuleError):
        service.import_records('patient-1')

def test_withdrawal_retraction_retry_and_earned_credit(service):
    connect(service)
    _, intro = authorize(service)
    credit = service.store.get('payment', 'patient-1')
    service.permission('patient-1', 'screening', False)
    assert service.profile('patient-1')['opportunities'] == []
    assert service.resources('patient-1') == []
    assert service.store.get('outbox', intro['id'])['state'] == 'PENDING'
    shared = service.team_introductions('team-1')[0]
    assert shared['state'] == 'WITHDRAWN' and 'approved_packet' not in shared
    assert service.store.get('outbox', intro['id'])['state'] == 'DELIVERED_IN_APP'
    service.process_outbox()
    assert len(service.store.all('outbox')) == 1
    assert service.store.get('payment', 'patient-1') == credit
    with pytest.raises(RuleError):
        service.authorize('patient-1', intro['id'], True)

def test_specific_introduction_withdrawal_does_not_stop_other_permissions(service):
    connect(service)
    _, intro = authorize(service)
    service.withdraw_introduction('patient-1', intro['id'])
    assert service.permitted('patient-1', 'screening')
    assert service.permitted('patient-1', 'records')
    assert 'approved_packet' not in service.team_introductions('team-1')[0]

def test_delete_removes_encrypted_identity_clinical_and_derived_payloads(service):
    connect(service)
    service.discuss('doctor-1', 'patient-1|' + HIGH, 'COMPLETED', 'Synthetic sensitive note')
    authorize(service)
    assert service.delete_records('patient-1')['earned_credit_preserved']
    for kind in ['identity', 'clinical', 'match', 'match_history', 'preview', 'discussion']:
        assert not any(row.get('patient_id') == 'patient-1' for row in service.store.all(kind))
    assert service.store.get('identity', 'patient-1') is None
    assert all('payload' not in row for row in service.store.all('introduction'))
    assert service.doctor_queue('doctor-1') == []
    assert service.profile('patient-1')['identity'] is None
    with pytest.raises(RuleError):
        service.permission('patient-1', 'screening', True)

def test_encrypted_at_rest_and_patient_kind_key_binding(service, tmp_path):
    connect(service)
    service.import_records('patient-1', followup=True)
    authorize(service)
    kinds = ['patient', 'identity', 'clinical', 'match', 'match_history', 'preview', 'introduction', 'audit', 'outbox', 'permission']
    persisted = json.dumps({kind: service.store.all(kind) for kind in kinds})
    for value in ['Alex Demo', 'alex@example.invalid', 'valueQuantity', 'normalized_value', '9.1', '11.2']:
        assert value not in persisted
    envelope = service.store.get('identity', 'patient-1')
    assert service.vault.open('patient-1', 'identity', envelope)['name'] == 'Alex Demo'
    assert service.vault.seal('patient-1', 'identity', {'x': 1}) != service.vault.seal('patient-1', 'identity', {'x': 1})
    for owner, kind in [('patient-2', 'identity'), ('patient-1', 'clinical')]:
        with pytest.raises(InvalidTag):
            service.vault.open(owner, kind, envelope)
    with pytest.raises(InvalidTag):
        Vault(tmp_path / 'other.key').open('patient-1', 'identity', envelope)

@pytest.mark.parametrize('money,benefit', [('$1000000 compensation.', 'Major possible benefit.'), ('$0 compensation.', 'Uncertain individual benefit.')])
def test_compensation_benefit_do_not_change_low_routing(service, money, benefit):
    source = synthetic_source('SYN-LOW')
    source['documents']['synthetic:compensation'] = money
    source['documents']['synthetic:benefits'] = benefit
    source['hash'] = fingerprint(source)
    service.publish(source, offline_spec(source), 'team-1')
    connect(service)
    assert service.preview('patient-1', LOW)
    assert not any(x['listing_id'] == LOW for x in service.store.all('discussion'))

def test_seed_does_not_overwrite_amended_versions(service):
    source = synthetic_source('SYN-LOW')
    spec = offline_spec(source)
    spec['generated']['risk_route'] = 'UNKNOWN'
    service.publish(source, spec, 'team-1')
    seed(service)
    assert service.store.get('listing', LOW)['version'] == 2
    assert service.store.get('listing', LOW)['risk'] == 'UNKNOWN'
