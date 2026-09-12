import time

class FreshnessGate:
    def __init__(self, stale_after):
        self.stale_after = stale_after

    def evaluate(self, retrieved_at):
        age = max(0, time.time() - retrieved_at)
        if age > self.stale_after:
            return "STALE", age, "source data exceeded freshness threshold"
        return "FRESH", age, ""

class ConflictGate:
    def compare(self, previous, current):
        if not previous:
            return False, ""
        conflicts = []
        for key in ("id",):
            if key in previous and key in current and previous[key] != current[key]:
                conflicts.append(key)
        return bool(conflicts), ",".join(conflicts)
