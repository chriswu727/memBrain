"""Replay of host consolidation with a stand-in model. PAID: calls DeepSeek; needs DEEPSEEK_API_KEY.

In the product the host's own AI writes cues: it calls ``memory_consolidate`` without arguments, receives a batch
of earlier messages with instructions, and calls the tool again with the cues. No host AI is run here. A model
stands in for it and is given exactly what the tool returns, batch after batch, through the real tool and service,
until nothing is left. The cues this leaves in the stored brains can then be scored without a model by
``retrieval_recall.py`` (run it on the same ``--brains`` directory with a new ``--label`` and without ``--cues``).

This says whether the batch format and the instructions produce useful cues. It does not say whether a real host
calls the tool, when, or how well its own model follows the instructions.

    python evaluations/locomo/host_consolidation_replay.py --data locomo10.json --brains RECALL_RUN_DIR \
        --out RUN_DIR --ceiling 3 [--reset]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from consolidation_experiment import ENDPOINT, Ledger, MeteredTransport, read_key  # noqa: E402
from retrieval_recall import write_cues  # noqa: E402
from run_locomo import Model, log, sessions, start  # noqa: E402

STAND_IN = "deepseek-flash"
ROLE = ("You are an AI assistant with a memory plugin. You called its tool memory_consolidate without arguments and "
        "received the JSON result below. Reply with only the JSON arguments of your second call to that tool.")


def forget_progress(directory: Path) -> int:
    """Start the review of a stored brain's messages again. The product has no such operation: review progress
    only moves forward. This harness owns these synthetic brains and removes the row in their database."""
    from membrain.helpers import Principal
    from membrain.local_profile import load_profile
    from membrain.storage import Database

    profile = load_profile(directory)
    database = Database(profile.database_url)
    try:
        with database.transaction(Principal(profile.tenant_id, profile.principal_id)) as conn:
            return conn.execute("DELETE FROM memory_cue_progress").rowcount
    finally:
        close = getattr(database, "close", None)
        if close:
            close()


def replay(sample: dict, directory: Path, model: Model, out: Path, reset: bool) -> dict:
    from membrain import desktop, host
    from membrain.mcp_server import create_server

    path = out / f"replay-{sample['sample_id']}.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "batches": 0, "offered": 0, "cued": 0, "phrases": 0, "refused": 0, "unreadable": 0}
    if state.get("done"):
        return state
    start(directory)
    try:
        if reset and not state["batches"]:
            every = {turn["dia_id"]: [] for _, _, turns in sessions(sample) for turn in turns}
            log("reset", sample["sample_id"], write_cues(sample, directory, every), "progress rows removed:",
                forget_progress(directory))
        with host.ready_client(directory) as client:
            # The stored brains are paused for the host so that questions are never recorded; the service is not.
            server = create_server(client, directory=None)

            def call(arguments):
                return asyncio.run(server.call_tool("memory_consolidate", arguments))[1]

            while True:
                batch = call({})
                if "error" in batch:
                    raise SystemExit(f"The tool refused to hand out a batch: {batch}")
                if not batch["messages"]:
                    break
                reply = model.chat([{"role": "system", "content": ROLE},
                                    {"role": "user", "content": json.dumps(batch, ensure_ascii=False)}],
                                   json_mode=True, max_tokens=4000)
                try:
                    arguments = json.loads(reply.get("content") or "")
                    cues = arguments.get("cues") if isinstance(arguments, dict) else None
                except ValueError:
                    arguments, cues = {}, None
                if not isinstance(cues, list):
                    state["unreadable"] += 1
                    cues = []
                # Until runtime d9c1a70 the batch carried a number the second call had to repeat, and the stand-in
                # repeated a different one for 33 of 299 batches (``wrong_number`` in the first replay's counts).
                result = call({"cues": cues})
                if "error" in result:  # Malformed entries: the batch is passed over, as a host giving up would.
                    state["refused"] += 1
                    result = call({"cues": []})
                    if "error" in result:
                        raise SystemExit(f"The tool refused an empty review: {result}")
                state["batches"] += 1
                state["offered"] += len(batch["messages"])
                state["cued"] += result["indexed"]
                state["phrases"] += sum(len(entry.get("cues") or []) for entry in cues if isinstance(entry, dict))
                path.write_text(json.dumps(state, indent=1), encoding="utf-8")
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass
    state["done"] = True
    path.write_text(json.dumps(state, indent=1), encoding="utf-8")
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", required=True)
    parser.add_argument("--brains", required=True, help="A retrieval_recall.py run directory with stored brains")
    parser.add_argument("--out", required=True)
    parser.add_argument("--conversations", default="", help="Comma-separated indexes; default all ten")
    parser.add_argument("--ceiling", type=float, required=True, help="Spending ceiling in CNY for this run directory")
    parser.add_argument("--reset", action="store_true", help="Remove the cues the stored turns already have first")
    args = parser.parse_args()
    read_key()
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    selected = [data[int(index)] for index in args.conversations.split(",")] if args.conversations else data
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(out / "ledger.json", args.ceiling)
    ledger.phase = "stand-in for the host AI"
    model = Model(ENDPOINT, STAND_IN, cap=2000)
    model.http = httpx.Client(timeout=300, transport=MeteredTransport(ledger))
    for sample in selected:
        state = replay(sample, Path(args.brains) / f"brain-{sample['sample_id']}", model, out, args.reset)
        log(sample["sample_id"], state, "spent", ledger.state["spent_cny"])


if __name__ == "__main__":
    main()
