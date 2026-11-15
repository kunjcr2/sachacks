"""Only public registry records and deliberately synthetic documents enter extraction."""
import hashlib
import json
from datetime import datetime, timezone
from .ctgov import fetch_trial, trial_preview

def fingerprint(source):
    # Retrieval time is metadata, not a source revision.
    body = {k: v for k, v in source.items() if k not in {'retrieved_at', 'hash'}}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()

def synthetic_rules(source_id):
    def numeric(field, low, high, unit, quote):
        return dict(id=field, type='inclusion', field=field, operator='between' if high is not None else 'gte',
                    min=low, max=high, unit=unit, source_text=quote)
    def boolean(field, quote, excluded=False):
        return dict(id=field, type='exclusion' if excluded else 'inclusion', field=field, operator='present', source_text=quote)
    age = numeric('age', 40 if source_id in {'SYN-HIGH', 'SYN-REMATCH'} else 30, 70 if source_id in {'SYN-HIGH', 'SYN-REMATCH'} else 75,
                  'years', 'Age between 40 and 70 years.' if source_id in {'SYN-HIGH', 'SYN-REMATCH'} else 'Age between 30 and 75 years.')
    rules = [age, boolean('dx_t2dm', 'Type 2 diabetes is required.')]
    if source_id == 'SYN-LOW':
        return rules + [numeric('hba1c', 7, 12.5, '%', 'HbA1c must be between 7% and 12.5%.'),
                        numeric('bmi', 27, 40, 'kg/m2', 'BMI between 27 and 40 kg/m2.')]
    if source_id == 'SYN-UNKNOWN':
        return rules + [numeric('sbp', 130, 160, 'mmHg', 'Systolic blood pressure between 130 and 160 mmHg.'),
                        numeric('bmi', 25, 40, 'kg/m2', 'BMI between 25 and 40 kg/m2.')]
    low, high = (7.5, 10) if source_id == 'SYN-REMATCH' else (8.5, 12)
    return rules + [numeric('hba1c', low, high, '%', f'HbA1c must be between {low:g}% and {high:g}%.'),
                    numeric('egfr', 45 if source_id == 'SYN-REMATCH' else 60, None, 'mL/min/1.73m2',
                            'eGFR at least 45 mL/min/1.73m2.' if source_id == 'SYN-REMATCH' else 'eGFR at least 60 mL/min/1.73m2.'),
                    numeric('bmi', 25, 40, 'kg/m2', 'BMI between 25 and 40 kg/m2.'),
                    boolean('rx_metformin', 'Active metformin treatment is required.'),
                    boolean('rx_insulin', 'Current insulin use is excluded.', True),
                    boolean('pregnant', 'Current pregnancy is excluded.', True)]

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
    eligibility = '\n'.join(rule['source_text'] for rule in synthetic_rules(source_id))
    purposes = {
        'SYN-LOW': 'Understand how nutrition education supports daily routines in adults with type 2 diabetes.',
        'SYN-HIGH': 'Evaluate an investigational add-on treatment in adults with type 2 diabetes taking metformin.',
        'SYN-UNKNOWN': 'Study the relationship between blood pressure, metabolic health and daily activity in type 2 diabetes.',
        'SYN-REMATCH': 'Study glucose management in adults with type 2 diabetes whose HbA1c is between 7.5% and 10%.',
    }
    docs = {
        'registry:eligibility': eligibility,
        'synthetic:purpose': purposes[source_id],
        'synthetic:participation': 'One 30-minute research visit and one questionnaire.',
        'synthetic:importance': 'Research importance: learning about patient experiences.',
    }
    if risk != 'UNKNOWN':
        docs['synthetic:risks'] = ('LOW risk designation in this synthetic protocol. Questionnaire discomfort is possible.'
                                  if risk == 'LOW' else 'HIGH risk designation in this synthetic protocol. Investigational treatment side effects and uncertainties require discussion.')
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
