"""Store held-out LoCoMo conversations at their session dates exactly as time_depth_recall.py stores the development
ones (its ``store``), then check the dates as it does (``check_dates``). No model call; embedding is local.

    python store_heldout.py RUN_DIR locomo10.json MODEL_CACHE 3,4,5,6,7,8,9
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "REPOSITORY/evaluations/locomo")
import time_depth_recall as t  # noqa: E402


def main():
    out, data_path, cache = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    assert "locomo-time-depth-heldout-" in str(out), out
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    selected = [data[int(index)] for index in sys.argv[4].split(",")]
    out.mkdir(parents=True, exist_ok=True)
    for sample in selected:
        directory = out / f"brain-{sample['sample_id']}"
        started = time.monotonic()
        events = t.store(sample, directory, cache)
        t.log("stored", sample["sample_id"], len(events), "events", round(time.monotonic() - started, 1), "s")
    print(json.dumps(t.check_dates([s for s in selected if (out / f"brain-{s['sample_id']}" / "events.json").exists()],
                                   out), indent=2), flush=True)


if __name__ == "__main__":
    main()
