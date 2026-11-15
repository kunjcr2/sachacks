"""Conservative source fidelity checks; semantic verification remains a human step."""
import re
from rematch.common.fields import FIELDS


def validate_criteria(criteria,eligibility_text,publication=False):
    errors = []
    for c in criteria:
        if c.source_text not in eligibility_text:
            errors.append(f"{c.id}: source quotation is not verbatim")
        if c.field not in FIELDS and c.field!="unmapped":
            errors.append(f"{c.id}: unsupported field; use unmapped")
        # Remove simple numeric ranges before testing for compound logic.
        text = re.sub(r"between\s+[\d.]+\s*%?\s+and\s+[\d.]+", "range", c.source_text, flags=re.I)
        if c.field!="unmapped" and re.search(r"\b(and|or|unless|except|prior|within|either)\b",text,re.I):
            errors.append(f"{c.id}: compound/temporal clause needs manual mapping as unmapped")
        if publication and c.review_status!="verified":
            errors.append(f"{c.id}: human verification required")
    if errors:
        raise ValueError("; ".join(errors))
    return criteria
