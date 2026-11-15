from datetime import date, timedelta
from pathlib import Path
import json

T0 = date(2026, 11, 15)


class DemoClock:
    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            self.set(T0)

    def now(self) -> date:
        return date.fromisoformat(json.loads(self.path.read_text())["today"])

    def set(self, value: date) -> date:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({"today": value.isoformat()}))
        temp.replace(self.path)
        return value

    def advance(self, days: int) -> date:
        if not 0 <= days <= 365:
            raise ValueError("Advance must be between 0 and 365 days")
        return self.set(self.now() + timedelta(days=days))
