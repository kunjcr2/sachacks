def canonical_unit(unit: str | None) -> str | None:
    aliases = {"µmol/L": "umol/L", "μmol/L": "umol/L", "mL/min/1.73m²": "mL/min/1.73m2",
               "kg/m²": "kg/m2", "percent": "%", "a": "years", "mm[Hg]": "mmHg"}
    return aliases.get(unit, unit)


def normalize(value: float, unit: str | None, target: str | None, field: str | None = None) -> tuple[float, bool]:
    source, target = canonical_unit(unit), canonical_unit(target)
    if source == target:
        return value, False
    if (source,target)==("mmol/L","mg/dL") and field not in {None,"glucose"}:
        raise ValueError("Molar conversion is analyte-specific; this field is unsupported")
    conversions = {("mmol/mol", "%"): lambda x: x / 10.929 + 2.15,
                   ("%", "mmol/mol"): lambda x: (x - 2.15) * 10.929,
                   ("mmol/L", "mg/dL"): lambda x: x * 18.016,
                   ("umol/L", "mg/dL"): lambda x: x / 88.4,
                   ("mg/dL", "umol/L"): lambda x: x * 88.4}
    try:
        return conversions[(source, target)](value), True
    except KeyError:
        raise ValueError(f"Incompatible unit: {unit} (expected {target})") from None
