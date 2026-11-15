"""Conservative automated checks for the synthetic prototype, not clinical certification."""
import re
from rematch.common.fields import FIELDS
from rematch.common.units import canonical_unit

def validate_criteria(criteria, eligibility_text, publication=False):
    errors = []
    for c in criteria:
        if c.source_text not in eligibility_text:
            errors.append(f"{c.id}: source quotation is not verbatim")
        if c.source_location != 'registry:eligibility':
            errors.append(f'{c.id}: unsupported criterion source location')
        if c.field not in FIELDS:
            errors.append(f"{c.id}: unsupported field requires follow-up")
            continue
        text = re.sub(r"between\s+[\d.]+\s*%?\s+and\s+[\d.]+", "range", c.source_text, flags=re.I)
        if re.search(r"\b(and|or|unless|except|prior|within|either)\b", text, re.I):
            errors.append(f"{c.id}: compound/temporal logic requires follow-up")
        if canonical_unit(c.unit) != FIELDS[c.field].unit:
            errors.append(f"{c.id}: unexpected unit")
        numbers = [float(x) for x in re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", c.source_text)]
        for value in (c.min, c.max, c.value if type(c.value) in (int, float) else None):
            if value is not None and float(value) not in numbers:
                errors.append(f"{c.id}: threshold absent from source")
        if re.search(r"\b(excluded|exclusion|ineligible)\b", c.source_text, re.I) and c.type != "exclusion":
            errors.append(f"{c.id}: exclusion polarity disagrees with source")
        if c.type == 'exclusion' and not re.search(r'\b(excluded|exclusion|ineligible)\b', c.source_text, re.I):
            errors.append(f'{c.id}: exclusion polarity has no explicit support')
        if c.operator in {'between', 'gte', 'gt', 'lte', 'lt'}:
            # Fail closed outside simple atomic numeric grammar. A model review
            # alone cannot turn arbitrary prose into a supported executable rule.
            names = {'age': 'Age', 'hba1c': 'HbA1c', 'egfr': 'eGFR', 'bmi': 'BMI',
                     'sbp': 'Systolic blood pressure', 'dbp': 'Diastolic blood pressure',
                     'creatinine': 'Creatinine', 'alt': 'ALT', 'cpeptide': 'C-peptide'}
            name = names.get(c.field)
            pattern = (re.escape(name) + r'\s+(?:must be\s+)?(?:(between|at least|at most|greater than|less than)\s+)?'
                       r'(\d+(?:\.\d+)?)\s*(?:%\s*)?(?:(?:and|to)\s+(\d+(?:\.\d+)?))?\s*(.*?)\.?') if name else ''
            parsed = re.fullmatch(pattern, c.source_text, flags=re.I) if pattern else None
            if not parsed:
                errors.append(f'{c.id}: unsupported numeric source grammar')
            else:
                word, first, second, unit = parsed.groups()
                expected = 'between' if second else {'at least': 'gte', 'at most': 'lte', 'greater than': 'gt', 'less than': 'lt'}.get((word or '').lower())
                low = c.min if c.min is not None else c.value
                high = c.max if c.max is not None else c.value
                if expected != c.operator or (expected in {'between', 'gte', 'gt'} and low != float(first)) or (expected in {'lte', 'lt'} and high != float(first)) or (second and high != float(second)):
                    errors.append(f'{c.id}: operator/bounds disagree with source')
                if canonical_unit(unit.strip()) != FIELDS[c.field].unit:
                    errors.append(f'{c.id}: source unit disagrees with canonical unit')
        elif c.operator in {'eq', 'in'}:
            errors.append(f'{c.id}: categorical source mapping requires follow-up')
        elif c.field not in FIELDS or FIELDS[c.field].kind not in {'condition', 'medication'}:
            errors.append(f'{c.id}: boolean rule on a nonboolean field')
        elif c.operator != 'present' or not re.search(r'\b(required|excluded)\b', c.source_text, re.I):
            errors.append(f'{c.id}: unsupported boolean source grammar')
        else:
            names = {'dx_t2dm': 'Type 2 diabetes', 'dx_ckd': 'Chronic kidney disease', 'dx_htn': 'Hypertension',
                     'dx_hf': 'Heart failure', 'pregnant': 'Current pregnancy',
                     **{'rx_' + drug: '(?:Active |Current )?' + drug + '(?: treatment| use)?' for drug in ['metformin', 'insulin', 'sglt2i', 'glp1ra']}}
            phrase = names.get(c.field, '(?!)') + (r' is excluded\.' if c.type == 'exclusion' else r' is required\.')
            if not re.fullmatch(phrase, c.source_text, re.I):
                errors.append(f'{c.id}: boolean field/meaning disagrees with source')
        # The prototype cannot source-validate inferred time windows or screening exceptions.
        if c.recency_days is not None or c.assessment_stage != "preliminary" or c.central_lab_required or c.fasting_required:
            errors.append(f"{c.id}: unsupported rule modifier requires follow-up")
    if errors:
        raise ValueError("; ".join(errors))
    return criteria

def validate_generated(generated, source):
    errors = []
    try:
        validate_criteria(generated.criteria, source['eligibility'])
    except ValueError as exc:
        errors.append(str(exc))
    if len({c.id for c in generated.criteria}) != len(generated.criteria):
        errors.append('Duplicate criterion IDs')
    for line in source['eligibility'].splitlines():
        if line.strip() and not any(line.strip() in c.source_text for c in generated.criteria):
            errors.append('Incomplete protocol coverage: ' + line.strip())
    if generated.unmapped:
        errors.append('Unmapped clauses require follow-up')
    for key in ['purpose', 'participation', 'risks', 'benefits', 'compensation', 'importance']:
        claim = getattr(generated, key)
        if claim and (claim.location not in source['documents'] or not claim.quote or claim.quote not in source['documents'][claim.location]):
            errors.append(key + ': unsupported quotation/location')
    return errors

def supported_risk(generated, source):
    claim = generated.risk_evidence
    if not claim or claim.location not in source['documents'] or claim.quote not in source['documents'][claim.location]:
        return 'UNKNOWN'
    text = claim.quote.lower()
    if generated.risk_route == 'LOW':
        if not re.search(r'\blow[- ]risk\b', text) or re.search(r'\b(high|higher|unknown|not|uncertain|conflict)\b', text):
            return 'UNKNOWN'
        # A conflicting designation elsewhere in the supplied source also fails closed.
        if any(re.search(r'\b(?:high|higher)[- ]risk\b', doc, re.I) for doc in source['documents'].values()):
            return 'UNKNOWN'
        return 'LOW'
    return generated.risk_route if generated.risk_route == 'HIGH' else 'UNKNOWN'
