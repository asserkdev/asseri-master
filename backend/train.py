from __future__ import annotations

import json
from pathlib import Path

from .memory import MemoryStore


def run_training(memory_path: Path) -> dict:
    memory = MemoryStore(memory_path)
    state = memory._state_no_lock(user_id=None)  # noqa: SLF001
    experiences = state.get("experiences", [])
    topic_stats = state.get("topic_stats", {})

    intent_counts: dict[str, int] = {}
    avg_conf = 0.0
    if isinstance(experiences, list) and experiences:
        total = 0.0
        for row in experiences:
            if not isinstance(row, dict):
                continue
            intent = str(row.get("intent", "unknown"))
            intent_counts[intent] = int(intent_counts.get(intent, 0)) + 1
            total += float(row.get("confidence", 0.0))
        avg_conf = total / max(len(experiences), 1)

    report = {
        "status": "ok",
        "experience_count": len(experiences) if isinstance(experiences, list) else 0,
        "intent_distribution": intent_counts,
        "topic_count": len(topic_stats) if isinstance(topic_stats, dict) else 0,
        "average_confidence": round(avg_conf, 4),
    }
    return report


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    memory_path = root / "backend" / "data" / "memory.json"
    report = run_training(memory_path)
    out_path = root / "backend" / "data" / "training_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

