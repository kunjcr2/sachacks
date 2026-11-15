"""Reproducible, declared synthetic study material and fake accounts."""
from rematch.common.schemas import GeneratedStudy, Criterion, BriefClaim
from rematch.extraction.sources import synthetic_source
from rematch.extraction.validate import validate_generated

def offline_spec(source):
    if source['kind'] != 'synthetic':
        raise ValueError('Offline fixtures exist only for declared synthetic studies')
    claim = lambda key: BriefClaim(quote=source['documents'][key], location=key) if key in source['documents'] else None
    criteria = [Criterion(id='age', type='inclusion', field='age', operator='between', min=18, max=75,
                          unit='years', source_text='Age between 18 and 75 years.')]
    if source['id'] == 'SYN-REMATCH':
        criteria.append(Criterion(id='hba1c', type='inclusion', field='hba1c', operator='between', min=7.5, max=10,
                                  unit='%', source_text='HbA1c must be between 7.5% and 10%.'))
    risk = 'HIGH' if source['id'] == 'SYN-HIGH' else 'UNKNOWN' if source['id'] == 'SYN-UNKNOWN' else 'LOW'
    generated = GeneratedStudy(criteria=criteria, purpose=claim('synthetic:purpose'),
        participation=claim('synthetic:participation'), risks=claim('synthetic:risks'),
        benefits=claim('synthetic:benefits'), compensation=claim('synthetic:compensation'),
        importance=claim('synthetic:importance'), risk_route=risk, risk_evidence=claim('synthetic:risks'), unmapped=[])
    errors = validate_generated(generated, source)
    return dict(generated=generated.model_dump(mode='json'), errors=errors,
                state='BLOCKED' if errors else 'VALIDATED_FOR_DEMO',
                model=None, review={'consistent': not errors, 'errors': errors},
                prompt_version='declared-synthetic-v1', schema_version='central-study-v1',
                source_hash=source['hash'], execution='offline_synthetic_fixture')

def seed(service):
    if service.store.get('meta', 'seeded'):
        return
    for source_id in ['SYN-LOW', 'SYN-HIGH', 'SYN-UNKNOWN', 'SYN-REMATCH']:
        source = synthetic_source(source_id)
        service.store.put('source', source_id, source)
        service.publish(source, offline_spec(source), 'team-1')
    if not service.store.get('patient', 'patient-1'):
        service.onboard(dict(name='Alex Demo', contact_method='email', contact='alex@example.invalid', assigned_pcp='doctor-1'), 'patient-1')
    if not service.store.get('patient', 'patient-2'):
        service.onboard(dict(name='Sam Example', contact_method='phone', contact='555-0102', assigned_pcp=None), 'patient-2')
    service.store.put('meta', 'seeded', {'schema': 'central-v1'})

def fhir_fixture(patient_id, today, followup=False):
    def observation(key, value, unit):
        return dict(resourceType='Observation', id=f'synthetic-{key}-{today}', subject={'reference': f'Patient/{patient_id}'},
                    code={'coding': [{'code': key}]}, effectiveDateTime=today,
                    valueQuantity={'value': value, 'unit': unit}, method={'text': 'STANDARD'})
    return dict(resourceType='Bundle', type='collection', entry=[
        {'resource': observation('age', 58, 'years')},
        {'resource': observation('hba1c', 9.1 if followup else 11.2, '%')}],
        provenance='Local synthetic FHIR-shaped fixture; simulated Epic authorization, no external connection')
