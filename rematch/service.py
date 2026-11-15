from datetime import date, timedelta, datetime, timezone
from functools import wraps
import hashlib
import json
import os
import uuid
from rematch.common.config import RUNTIME, KEYS
from rematch.common.crypto import Vault
from rematch.common.db import Store
from rematch.common.fhir import Bundle
from rematch.common.schemas import TrialBundle, GeneratedStudy, Identity
from rematch.clinic.matching.engine import match
from rematch.clinic.matching.snapshot import PatientSnapshot
from rematch.extraction.validate import validate_generated, supported_risk

class RuleError(ValueError):
    pass

def locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.store.lock:
            return method(self, *args, **kwargs)
    return call

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

BRIEF = [('purpose', 'Purpose'), ('participation', 'What participation involves'),
         ('risks', 'Main risks and uncertainties'), ('benefits', 'Possible benefits'),
         ('compensation', 'Costs and compensation')]
MISSING = 'Not provided in the available study information.'

class Service:
    def __init__(self, store=None, vault=None):
        self.store = store or Store(RUNTIME / 'rematch-central-v1.sqlite')
        self.vault = vault or Vault(KEYS / 'central-vault-v1.key')
        if not self.store.get('meta', 'clock'):
            self.store.put('meta', 'clock', {'today': '2026-11-15'})

    def today(self):
        return date.fromisoformat(self.store.get('meta', 'clock')['today'])

    def audit(self, action, actor, **references):
        self.store.put('audit', str(uuid.uuid4()), dict(action=action, actor=actor, references=references, at=self.today().isoformat()))

    def patient(self, pid):
        row = self.store.get('patient', pid)
        if not row:
            raise RuleError('Profile not found')
        return row

    def permitted(self, pid, kind):
        return self.store.get('permission', pid + ':' + kind, {}).get('granted', False)

    @locked
    def onboard(self, values, pid=None):
        pid = pid or 'patient-' + uuid.uuid4().hex[:12]
        if self.store.get('patient', pid):
            raise RuleError('Profile already exists')
        identity = Identity.model_validate({k: values[k] for k in ['name', 'contact_method', 'contact']}).model_dump()
        self.store.put('identity', pid, self.vault.seal(pid, 'identity', identity))
        self.store.put('patient', pid, dict(id=pid, assigned_pcp=values.get('assigned_pcp'), record_version=0, deleted=False,
                                          preferences={'research_matching': False}))
        credit = float(os.getenv('DEMO_ONBOARDING_CREDIT', '5'))
        self.store.put('payment', pid, dict(id=pid, type='onboarding_time_credit', amount=credit, currency='USD',
                       state='SIMULATED_EARNED', label='Onboarding time credit — no payment sent'))
        self.audit('onboard', pid, patient=pid)
        return pid

    @locked
    def permission(self, pid, kind, granted):
        patient = self.patient(pid)
        if granted and patient['deleted']:
            raise RuleError('Deleted records require a new profile')
        key = pid + ':' + kind
        previous = self.store.get('permission', key, {'version': 0})
        row = dict(patient_id=pid, kind=kind, version=previous['version'] + 1, granted=granted,
                   scope='ongoing synthetic screening' if kind == 'screening' else 'local simulated Epic imports',
                   recipient='ReMatch', at=self.today().isoformat(), revoked=not granted)
        self.store.put('permission', key, row)
        self.store.put('permission_history', key + ':' + str(row['version']), row)
        self.invalidate(pid=pid, retract=not granted)
        if kind == 'screening':
            patient['preferences']['research_matching'] = granted
            self.store.put('patient', pid, patient)
            if not granted:
                self.purge_clinical(pid)
        self.audit('permission', pid, patient=pid, kind=kind, version=row['version'])
        if granted:
            self.reassess(pid)
        return row

    def purge_clinical(self, pid):
        for row in self.store.all('clinical'):
            if row['patient_id'] == pid:
                self.store.delete('clinical', row['id'])
        for kind in ['match', 'match_history', 'preview']:
            for row in self.store.all(kind):
                if row['patient_id'] == pid:
                    self.store.delete(kind, row['id'])

    @locked
    def import_records(self, pid, followup=False):
        from rematch.seed import fhir_fixture
        patient = self.patient(pid)
        if not self.permitted(pid, 'records') or not self.permitted(pid, 'screening'):
            raise RuleError('Screening permission and simulated record authorization are required before import')
        bundle = fhir_fixture(pid, self.today().isoformat(), followup)
        Bundle.model_validate({key: bundle[key] for key in ['resourceType', 'type', 'entry']})
        version = patient['record_version'] + 1
        key = pid + ':' + str(version)
        self.store.put('clinical', key, dict(id=key, patient_id=pid, version=version,
                       source='local-synthetic-epic', effective_at=self.today().isoformat(),
                       ingested_at=datetime.now(timezone.utc).isoformat(), payload=self.vault.seal(pid, 'clinical', bundle)))
        patient['record_version'] = version
        self.store.put('patient', pid, patient)
        self.invalidate(pid=pid, retract=False)
        self.reassess(pid)
        self.audit('synthetic_import', pid, patient=pid, version=version)
        return {'record_version': version, 'source': bundle['provenance']}

    def resources(self, pid):
        resources = []
        for row in self.store.all('clinical'):
            if row['patient_id'] == pid:
                resources.extend(e['resource'] for e in self.vault.open(pid, 'clinical', row['payload'])['entry'])
        return resources

    @locked
    def clinical_summary(self, pid):
        self.patient(pid)
        snapshot = PatientSnapshot.from_fhir(pid, self.resources(pid))
        history = []
        for row in self.store.all('clinical'):
            if row['patient_id'] == pid:
                bundle = self.vault.open(pid, 'clinical', row['payload'])
                facts = PatientSnapshot.from_fhir(pid, [entry['resource'] for entry in bundle['entry']])
                history.append({'version': row['version'], 'effective_at': row['effective_at'], 'ingested_at': row['ingested_at'],
                                'facts': [fact.model_dump(mode='json') for fact in facts.facts.values()]})
        return {'current': [fact.model_dump(mode='json') for fact in snapshot.facts.values()], 'history': history}

    @locked
    def update_source(self, source, actor):
        old = self.store.get('source', source['id'])
        self.store.put('source', source['id'], source)
        if old and old['hash'] != source['hash']:
            for listing in self.store.all('listing'):
                if listing['study_id'] == source['id']:
                    listing['status'] = 'paused'
                    listing['pending_source_hash'] = source['hash']
                    self.store.put('listing', listing['id'], listing)
                    self.invalidate(listing_id=listing['id'], retract=False)
            self.audit('source_changed', actor, source=source['id'])

    @locked
    def publish(self, source, spec, owner, *, published=True):
        generated = GeneratedStudy.model_validate(spec['generated'])
        errors = validate_generated(generated, source)
        if errors or spec['state'] != 'VALIDATED_FOR_DEMO' or spec['source_hash'] != source['hash']:
            raise RuleError('Study is blocked: ' + '; '.join(errors or spec.get('errors', [])))
        listing_id = source['id'] + ':' + owner
        old = self.store.get('listing', listing_id)
        revision = digest({'source': source['hash'], 'spec': spec['generated'], 'state': spec['state'], 'published': published})
        if old and old['revision'] == revision and not old.get('pending_source_hash'):
            return old
        version = old['version'] + 1 if old else 1
        row = dict(id=listing_id, study_id=source['id'], version=version, revision=revision, owner=owner,
                   pi='Dr Morgan, PI' if owner == 'team-1' else 'Dr Rivera, PI',
                   site='Riverside Research Center' if owner == 'team-1' else 'Oakwood Research Site',
                   contact='research@example.invalid' if owner == 'team-1' else 'second@example.invalid',
                   status=source['status'] if published else 'draft', risk=supported_risk(generated, source), risk_evidence=generated.risk_evidence.model_dump() if generated.risk_evidence else None,
                   title=source['title'], source=source, specification=spec, payment_state='SIMULATED_PAID' if published else 'NOT_CHARGED')
        self.store.put('listing', listing_id, row)
        self.store.put('study_history', listing_id + ':' + str(version), row)
        if published:
            self.store.put('payment', listing_id, dict(id=listing_id, type='listing_fee', amount=float(os.getenv('DEMO_LISTING_FEE', '100')),
                           currency='USD', state='SIMULATED_PAID', label='Simulated payment — no charge'))
        self.invalidate(listing_id=listing_id, retract=False)
        for patient in self.store.all('patient'):
            self.reassess(patient['id'])
        self.audit('listing_published' if published else 'study_draft_saved', owner, listing=listing_id, version=version)
        return row

    def brief(self, listing):
        generated = listing['specification']['generated']
        lines = []
        for key, heading in BRIEF:
            claim = generated[key]
            text = claim['quote'] if claim else MISSING
            if key == 'benefits':
                text += ' No individual benefit is guaranteed.'
            lines.append({'heading': heading, 'text': text, 'source': claim})
        return lines

    def public_listing(self, listing):
        return {k: listing[k] for k in ['id', 'version', 'title', 'pi', 'site', 'contact', 'status', 'risk']} | {
            'brief': self.brief(listing), 'source_url': listing['source']['url'],
            'label': 'AI-generated study summary' if listing['specification']['model'] else 'Prepared study summary',
            'importance': listing['specification']['generated']['importance']}

    @locked
    def reassess(self, pid):
        patient = self.patient(pid)
        if not self.permitted(pid, 'screening') or patient['deleted']:
            return
        snapshot = PatientSnapshot.from_fhir(pid, self.resources(pid))
        for listing in sorted(self.store.all('listing'), key=lambda x: x['id']):
            source = listing['source']
            spec = listing['specification']
            if listing['status'] != 'recruiting' or spec['state'] != 'VALIDATED_FOR_DEMO':
                self.invalidate(pid=pid, listing_id=listing['id'], retract=False)
                continue
            trial = TrialBundle(trial_id=listing['study_id'], version=listing['version'], title=listing['title'],
                plain_language_summary='', source=source['kind'], source_ref=source['url'], status=listing['status'],
                last_updated=self.today(), raw_eligibility_text=source['eligibility'],
                criteria=spec['generated']['criteria'], visits_summary='')
            result = match(snapshot, trial, self.today()).model_dump(mode='json')
            key = pid + '|' + listing['id']
            stamp = digest({'result': result, 'record_version': patient['record_version'], 'revision': listing['revision'],
                            'permission': self.store.get('permission', pid + ':screening')['version'],
                            'records_permission': self.store.get('permission', pid + ':records', {}).get('version')})
            previous = self.store.get('match', key)
            if previous and previous['stamp'] == stamp:
                continue
            self.invalidate(pid=pid, listing_id=listing['id'], retract=False)
            row = dict(id=key, patient_id=pid, listing_id=listing['id'], study_version=listing['version'],
                       record_version=patient['record_version'], stamp=stamp, status=result['status'], risk=listing['risk'],
                       payload=self.vault.seal(pid, 'match', result))
            self.store.put('match', key, row)
            self.store.put('match_history', key + ':' + stamp, row | {'id': key + ':' + stamp})
            if result['status'] == 'POTENTIAL_MATCH' and listing['risk'] != 'LOW':
                self.store.put('discussion', key, dict(id=key, patient_id=pid, listing_id=listing['id'],
                    stamp=stamp, pcp=patient['assigned_pcp'], outcome='PENDING', study_version=listing['version'],
                    at=self.today().isoformat()))
            self.audit('reassessment', 'system', patient=pid, listing=listing['id'], stamp=stamp)

    def invalidate(self, pid=None, listing_id=None, retract=False):
        for kind in ['preview', 'discussion']:
            for row in self.store.all(kind):
                if (pid is None or row['patient_id'] == pid) and (listing_id is None or row['listing_id'] == listing_id):
                    row['invalid'] = True
                    self.store.put(kind, row['id'], row)
        for row in self.store.all('introduction'):
            if (pid is None or row['patient_id'] == pid) and (listing_id is None or row['listing_id'] == listing_id):
                if row['state'] not in {'WITHDRAWN', 'CLOSED'}:
                    row['needs_reauthorization'] = True
                    if retract:
                        row['state'] = 'WITHDRAWN'
                        row['authorization']['revoked'] = True
                        row.pop('payload', None)
                        self.store.put('outbox', row['id'], dict(id=row['id'], introduction_id=row['id'], recipient=row['owner'], action='RETRACTION', state='PENDING'))
                    self.store.put('introduction', row['id'], row)

    def require_match(self, pid, listing_id):
        self.reassess(pid)
        listing = self.store.get('listing', listing_id)
        row = self.store.get('match', pid + '|' + listing_id)
        if not listing or listing['status'] != 'recruiting' or not row or row['status'] != 'POTENTIAL_MATCH' or not self.permitted(pid, 'screening'):
            raise RuleError('A current potential match to an active study and screening permission are required')
        if listing['risk'] != 'LOW':
            discussion = self.store.get('discussion', row['id'], {})
            if discussion.get('invalid') or discussion.get('stamp') != row['stamp'] or discussion.get('outcome') != 'COMPLETED' or not self.patient(pid)['assigned_pcp']:
                raise RuleError('Your doctor must complete the discussion before an introduction')
        return row, listing

    @locked
    def discuss(self, doctor, key, outcome, note):
        row = self.store.get('discussion', key)
        if not row or row['pcp'] != doctor:
            raise RuleError('This discussion is not assigned to this doctor')
        self.reassess(row['patient_id'])
        row = self.store.get('discussion', key)
        if row.get('invalid') or not self.permitted(row['patient_id'], 'screening'):
            raise RuleError('Discussion is no longer current')
        row.update(outcome=outcome, note=self.vault.seal(row['patient_id'], 'discussion', {'note': note}), at=self.today().isoformat())
        self.store.put('discussion', key, row)
        # Any changed discussion revokes outstanding previews.
        for preview in self.store.all('preview'):
            if preview['patient_id'] == row['patient_id'] and preview['listing_id'] == row['listing_id']:
                preview['invalid'] = True
                self.store.put('preview', preview['id'], preview)
        return {'outcome': outcome}

    @locked
    def preview(self, pid, listing_id):
        row, listing = self.require_match(pid, listing_id)
        identity = self.vault.open(pid, 'identity', self.store.get('identity', pid))
        result = self.vault.open(pid, 'match', row['payload'])
        packet = dict(name=identity['name'], preferred_contact={'method': identity['contact_method'], 'value': identity['contact']},
                      screening_summary=[{'criterion_id': c['criterion_id'], 'status': c['status'],
                                          'explanation': c['explanation']} for c in result['criteria']])
        key = uuid.uuid4().hex
        preview = dict(id=key, patient_id=pid, listing_id=listing_id, owner=listing['owner'], stamp=row['stamp'],
            study_version=listing['version'], record_version=row['record_version'], recipient={'pi': listing['pi'], 'site': listing['site'], 'contact': listing['contact']},
            purpose='One introduction for study-team formal screening; no full chart disclosure.',
            screening_permission_version=self.store.get('permission', pid + ':screening')['version'],
            record_authorization_version=self.store.get('permission', pid + ':records', {}).get('version'),
            at=self.today().isoformat(), expires_at=(datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
            payload=self.vault.seal(pid, 'preview', packet))
        self.store.put('preview', key, preview)
        return {k: v for k, v in preview.items() if k != 'payload'} | {'exact_packet': packet}

    @locked
    def authorize(self, pid, preview_id, confirmed):
        preview = self.store.get('preview', preview_id)
        if not confirmed or not preview or preview['patient_id'] != pid or preview.get('invalid'):
            raise RuleError('Explicit patient permission for a current preview is required')
        row, listing = self.require_match(pid, preview['listing_id'])
        if preview['stamp'] != row['stamp'] or preview['at'] != self.today().isoformat() or datetime.now(timezone.utc) > datetime.fromisoformat(preview['expires_at']):
            raise RuleError('Preview expired or records changed; preview again')
        old = self.store.get('introduction', preview_id)
        if old:
            if old['authorization']['revoked']:
                raise RuleError('This authorization was revoked')
            return {'id': old['id'], 'state': old['state']}
        authorization = dict(version=1, patient_id=pid, recipient=listing['owner'], listing_id=listing['id'],
            study_version=listing['version'], record_version=row['record_version'], preview_id=preview_id,
            screening_permission_version=preview['screening_permission_version'],
            record_authorization_version=preview['record_authorization_version'],
            scope='exact preview packet', purpose=preview['purpose'], at=self.today().isoformat(), revoked=False)
        packet = self.vault.open(pid, 'preview', preview['payload'])
        intro = dict(id=preview_id, patient_id=pid, listing_id=listing['id'], owner=listing['owner'],
            state='SHARED', enrollment='NOT_REPORTED', authorization=authorization,
            needs_reauthorization=False, recipient=preview['recipient'],
            payload=self.vault.seal(pid, 'introduction', packet))
        self.store.put('introduction', preview_id, intro)
        self.store.put('outbox', preview_id, dict(id=preview_id, introduction_id=preview_id, recipient=listing['owner'], action='INTRODUCTION', state='DELIVERED_IN_APP'))
        self.audit('introduction_authorized', pid, introduction=preview_id, consent_version=1)
        return {'id': preview_id, 'state': 'SHARED'}

    @locked
    def process_outbox(self):
        for row in self.store.all('outbox'):
            if row['state'] == 'PENDING':
                row['state'] = 'DELIVERED_IN_APP'
                self.store.put('outbox', row['id'], row)

    def team_introductions(self, owner):
        self.process_outbox()
        result = []
        for row in self.store.all('introduction'):
            if row['owner'] != owner:
                continue
            visible = {k: row[k] for k in ['id', 'listing_id', 'state', 'enrollment', 'needs_reauthorization', 'authorization']}
            if row['state'] != 'WITHDRAWN' and not row['authorization']['revoked'] and row.get('payload'):
                visible['approved_packet'] = self.vault.open(row['patient_id'], 'introduction', row['payload'])
            result.append(visible)
        return result

    @locked
    def followup(self, owner, intro_id, action):
        row = self.store.get('introduction', intro_id)
        if not row or row['owner'] != owner:
            raise RuleError('Introduction not available to this study team')
        if row['state'] in {'WITHDRAWN', 'CLOSED'} or row.get('needs_reauthorization'):
            raise RuleError('Introduction withdrawn, closed, or needs new patient permission')
        if action == 'ENROLLED':
            if row['state'] != 'SCREENING_INVITED':
                raise RuleError('Record a formal screening invitation before a simulated enrollment outcome')
            row['enrollment'] = 'SIMULATED_ENROLLED'
        else:
            allowed = {'SHARED': {'ACKNOWLEDGED', 'NEED_INFO', 'SCREENING_INVITED', 'CLOSED'},
                       'ACKNOWLEDGED': {'NEED_INFO', 'SCREENING_INVITED', 'CLOSED'},
                       'NEED_INFO': {'ACKNOWLEDGED', 'SCREENING_INVITED', 'CLOSED'},
                       'SCREENING_INVITED': {'CLOSED'}}
            if action not in allowed.get(row['state'], set()):
                raise RuleError('Invalid introduction transition')
            row['state'] = action
        self.store.put('introduction', intro_id, row)
        self.audit('study_team_outcome', owner, introduction=intro_id, outcome=action)
        return {'state': row['state'], 'enrollment': row['enrollment']}

    @locked
    def withdraw_introduction(self, pid, intro_id):
        row = self.store.get('introduction', intro_id)
        if not row or row['patient_id'] != pid:
            raise RuleError('Introduction not found')
        row['state'] = 'WITHDRAWN'
        row['authorization']['revoked'] = True
        row.pop('payload', None)
        self.store.put('introduction', intro_id, row)
        self.store.put('outbox', intro_id, dict(id=intro_id, introduction_id=intro_id, recipient=row['owner'], action='RETRACTION', state='PENDING'))
        return {'state': 'WITHDRAWN'}

    @locked
    def delete_records(self, pid):
        self.permission(pid, 'screening', False)
        self.permission(pid, 'records', False)
        self.store.delete('identity', pid)
        self.purge_clinical(pid)
        for kind in ['discussion', 'preview', 'match', 'match_history']:
            for row in self.store.all(kind):
                if row['patient_id'] == pid:
                    self.store.delete(kind, row['id'])
        for intro in self.store.all('introduction'):
            if intro['patient_id'] == pid:
                intro.pop('payload', None)
                self.store.put('introduction', intro['id'], intro)
        patient = self.patient(pid)
        patient['deleted'] = True
        self.store.put('patient', pid, patient)
        self.process_outbox()
        self.audit('stored_records_deleted', pid, patient=pid)
        return {'deleted': True, 'earned_credit_preserved': True}

    @locked
    def advance(self, days):
        self.store.put('meta', 'clock', {'today': (self.today() + timedelta(days=days)).isoformat()})
        for patient in self.store.all('patient'):
            self.reassess(patient['id'])
        return {'today': self.today().isoformat()}

    @locked
    def profile(self, pid):
        patient = self.patient(pid)
        self.reassess(pid)
        opportunities = []
        for row in self.store.all('match'):
            if row['patient_id'] != pid:
                continue
            listing = self.store.get('listing', row['listing_id'])
            if listing['status'] != 'recruiting':
                continue
            discussion = self.store.get('discussion', row['id'], {})
            waiting = row['status'] == 'POTENTIAL_MATCH' and listing['risk'] != 'LOW' and (discussion.get('invalid') or discussion.get('outcome') != 'COMPLETED')
            item = {'listing_id': listing['id'], 'status': row['status'], 'waiting_for_doctor': bool(waiting)}
            if waiting:
                item['message'] = 'Your doctor can help you review this opportunity.' if patient['assigned_pcp'] else 'Arrange a review with your usual doctor; no doctor is assigned.'
            else:
                item['study'] = self.public_listing(listing)
                item['reasons'] = self.vault.open(pid, 'match', row['payload'])['criteria']
            opportunities.append(item)
        return dict(patient=patient, today=self.today().isoformat(),
            identity=self.vault.open(pid, 'identity', self.store.get('identity', pid)) if not patient['deleted'] else None,
            permissions={kind: self.store.get('permission', pid + ':' + kind, {'granted': False, 'version': 0}) for kind in ['screening', 'records']},
            credit=self.store.get('payment', pid), opportunities=opportunities,
            introductions=[{k: row[k] for k in ['id', 'listing_id', 'state', 'enrollment', 'recipient', 'needs_reauthorization']}
                           for row in self.store.all('introduction') if row['patient_id'] == pid])

    @locked
    def doctor_queue(self, doctor):
        for patient in self.store.all('patient'):
            if patient['assigned_pcp'] == doctor:
                self.reassess(patient['id'])
        result = []
        for row in self.store.all('discussion'):
            if row['pcp'] != doctor or row.get('invalid'):
                continue
            listing = self.store.get('listing', row['listing_id'])
            if listing['status'] != 'recruiting':
                continue
            pid = row['patient_id']
            result.append({k: v for k, v in row.items() if k != 'note'} | {
                'identity': self.vault.open(pid, 'identity', self.store.get('identity', pid)),
                'study': self.public_listing(listing),
                'reasons': self.vault.open(pid, 'match', self.store.get('match', row['id'])['payload'])['criteria'],
                'note': self.vault.open(pid, 'discussion', row['note'])['note'] if row.get('note') else ''})
        return result
