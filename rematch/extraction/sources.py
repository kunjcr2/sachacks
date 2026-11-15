"""Only public registry records and deliberately synthetic documents enter extraction."""
import hashlib
import json
from datetime import datetime, timezone
from .ctgov import fetch_trial, trial_preview

def fingerprint(source):
    # Retrieval time is metadata, not a source revision.
    body = {k: v for k, v in source.items() if k not in {'retrieved_at', 'hash'}}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()

def synthetic_source(source_id):
    choices = {
        'SYN-LOW': ('Everyday Balance', 'LOW', 'Possible individual benefit: nutrition knowledge; no guaranteed benefit.', '$10 reimbursement; $20 compensation; no patient costs.'),
        'SYN-HIGH': ('Treatment Questions', 'HIGH', 'Individual benefit is uncertain; no guaranteed benefit.', '$0 reimbursement; $5 compensation; no patient costs.'),
        'SYN-UNKNOWN': ('Health Conversations', 'UNKNOWN', None, None),
        'SYN-REMATCH': ('ReNew T2D', 'LOW', None, '$15 compensation for time; no patient costs.'),
    }
    if source_id not in choices:
        raise ValueError('Unknown synthetic source')
    title, risk, benefit, compensation = choices[source_id]
    eligibility = 'Age between 18 and 75 years.'
    if source_id == 'SYN-REMATCH':
        eligibility += '\nHbA1c must be between 7.5% and 10%.'
    docs = {
        'registry:eligibility': eligibility,
        'synthetic:purpose': f'This fictional study explores {title.lower()}.',
        'synthetic:participation': 'One 30-minute research visit and one questionnaire.',
        'synthetic:importance': 'Research importance: learning about patient experiences.',
    }
    if risk != 'UNKNOWN':
        docs['synthetic:risks'] = ('Synthetic fixture designation: LOW risk for demo routing. Questionnaire discomfort is possible.'
                                  if risk == 'LOW' else 'Synthetic fixture designation: HIGH risk for demo routing. Investigational treatment side effects and uncertainties require discussion.')
    if benefit:
        docs['synthetic:benefits'] = benefit
    if compensation:
        docs['synthetic:compensation'] = compensation
    source = dict(id=source_id, title=title, kind='synthetic', status='recruiting', registry_sponsor=None,
                  url='Synthetic study-source fixture, not a real recruiting study', eligibility=eligibility,
                  documents=docs, retrieved_at=datetime.now(timezone.utc).isoformat())
    source['hash'] = fingerprint(source)
    return source

def public_source(nct_id, refresh=False):
    cached = fetch_trial(nct_id, refresh)
    view = trial_preview(cached)
    protocol = cached['record']['protocolSection']
    docs = {'registry:eligibility': view['eligibility']}
    constraints = []
    for field in ['minimum_age', 'maximum_age', 'sex']:
        if view.get(field) and view[field] not in {'N/A', 'ALL'}:
            constraints.append(field + ': ' + str(view[field]))
    # Registry demographic restrictions outside the narrative must not vanish.
    # Unsupported formats remain blocked rather than guessed from free text.
    if constraints:
        docs['registry:eligibility'] += '\n' + '\n'.join(constraints)
    desc = protocol.get('descriptionModule', {})
    if desc.get('briefSummary'):
        docs['registry:briefSummary'] = desc['briefSummary']
    if desc.get('detailedDescription'):
        docs['registry:detailedDescription'] = desc['detailedDescription']
    source = dict(id=nct_id, title=view['title'], kind='clinicaltrials.gov',
                  status='recruiting' if view['status'] in {'RECRUITING', 'ENROLLING_BY_INVITATION'} else 'closed',
                  registry_sponsor=protocol.get('sponsorCollaboratorsModule', {}).get('leadSponsor', {}).get('name'),
                  url=view['source_url'], eligibility=docs['registry:eligibility'], documents=docs,
                  retrieved_at=view['retrieved_at'])
    source['hash'] = fingerprint(source)
    return source
