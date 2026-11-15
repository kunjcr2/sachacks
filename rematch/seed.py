"""Reproducible, declared synthetic study material and fake accounts."""
from rematch.common.schemas import GeneratedStudy, Criterion, BriefClaim
from rematch.extraction.sources import synthetic_source, synthetic_rules
from rematch.extraction.validate import validate_generated

def offline_spec(source):
    if source['kind'] != 'synthetic':
        raise ValueError('Offline fixtures exist only for declared synthetic studies')
    claim = lambda key: BriefClaim(quote=source['documents'][key], location=key) if key in source['documents'] else None
    criteria = [Criterion(**rule) for rule in synthetic_rules(source['id'])]
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
    if service.store.get('meta', 'seeded', {}).get('seed_version') == 2:
        return
    for source_id in ['SYN-LOW', 'SYN-HIGH', 'SYN-UNKNOWN', 'SYN-REMATCH']:
        source = synthetic_source(source_id)
        service.update_source(source, 'system')
        service.publish(source, offline_spec(source), 'team-1', published=False)
    if not service.store.get('patient', 'patient-1'):
        service.onboard(dict(name='Alex Morgan', contact_method='email', contact='alex@example.invalid', assigned_pcp='doctor-1'), 'patient-1')
    if not service.store.get('patient', 'patient-2'):
        service.onboard(dict(name='Sam Example', contact_method='phone', contact='555-0102', assigned_pcp=None), 'patient-2')
    existing_identity = service.store.get('identity', 'patient-1')
    if existing_identity:
        identity = service.vault.open('patient-1', 'identity', existing_identity)
        if identity['name'] == 'Alex Demo':
            identity['name'] = 'Alex Morgan'
            service.store.put('identity', 'patient-1', service.vault.seal('patient-1', 'identity', identity))
    service.store.put('meta', 'seeded', {'schema': 'central-v1', 'seed_version': 2})

def fhir_fixture(patient_id, today, followup=False):
    def observation(key, value, unit):
        return dict(resourceType='Observation', id=f'synthetic-{key}-{today}', subject={'reference': f'Patient/{patient_id}'},
                    code={'coding': [{'code': key}]}, effectiveDateTime=today,
                    valueQuantity={'value': value, 'unit': unit}, method={'text': 'STANDARD'})
    def clinical(key, value, resource_type):
        return dict(resourceType=resource_type, id=f'synthetic-{key}-{today}', subject={'reference': f'Patient/{patient_id}'},
                    code={'coding': [{'code': key}]}, effectiveDateTime=today, valueBoolean=value)
    second = patient_id == 'patient-2'
    observations = [('age', 46 if second else 58, 'years'), ('hba1c', 9.1 if followup else 9.8 if second else 11.2, '%'),
                    ('egfr', 92 if second else 68, 'mL/min/1.73m2'), ('creatinine', .9 if second else 1.1, 'mg/dL'),
                    ('bmi', 29.2 if second else 31.4, 'kg/m2'), ('sbp', 132 if second else 138, 'mmHg'),
                    ('dbp', 82 if second else 84, 'mmHg'), ('alt', 22 if second else 24, 'U/L')]
    conditions = {'dx_t2dm': True, 'dx_htn': not second, 'dx_ckd': False, 'dx_hf': False, 'pregnant': False}
    medications = {'rx_metformin': True, 'rx_insulin': False, 'rx_sglt2i': False, 'rx_glp1ra': False}
    return dict(resourceType='Bundle', type='collection', entry=[
        *[{'resource': observation(*values)} for values in observations],
        *[{'resource': clinical(key, value, 'Condition')} for key, value in conditions.items()],
        *[{'resource': clinical(key, value, 'MedicationStatement')} for key, value in medications.items()]],
        provenance='Local synthetic FHIR-shaped fixture; simulated Epic authorization, no external connection')
