from datetime import timedelta
import pytest
from rematch.common.clock import DemoClock, T0
from rematch.common.units import normalize


def test_clock_persists(tmp_path):
    clock = DemoClock(tmp_path / "clock.json")
    assert clock.now() == T0
    clock.advance(90)
    assert DemoClock(clock.path).now() == T0 + timedelta(days=90)
    with pytest.raises(ValueError):
        clock.advance(-1)


@pytest.mark.parametrize("value,source,target,expected", [
    (53, "mmol/mol", "%", 53 / 10.929 + 2.15),
    (88.4, "µmol/L", "mg/dL", 1), (5, "mmol/L", "mg/dL", 90.08),
    (10, "%", "%", 10), (10, "%", "mmol/mol", (10-2.15)*10.929)])
def test_units(value, source, target, expected):
    assert normalize(value, source, target)[0] == pytest.approx(expected)


def test_incompatible_units():
    with pytest.raises(ValueError):
        normalize(10, "bananas", "%")
