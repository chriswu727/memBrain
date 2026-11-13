# The turn arm needs a runtime with the note-extraction model (membrain.extraction), removed after 77c1f841.
"""LoCoMo answer accuracy with and without consolidation into notes. PAID: calls DeepSeek; needs DEEPSEEK_API_KEY.

Three arms on the same conversations, each in its own installations, answered and judged like ``run_locomo.py``:

- ``plain``:   the plugin path as shipped. Messages only, no notes.
- ``turn``:    note extraction after every stored turn with ``deepseek-flash`` (the shipped extraction path).
- ``session``: one consolidation call with ``deepseek-v4-pro`` after each finished session: it reads the notes kept
               so far and the session, and adds or replaces notes, each bound to the turns it rests on. This arm
               exists only in this harness; it is the experiment.
- ``cues``:    messages only, with the cues a model wrote earlier (``--cues``, a directory of
               ``cues-<conversation>.json`` from ``cue_enrichment_simulation.py``) attached to the stored turns, so
               recall can reach a turn through them. Attaching them makes no model call.

Every request goes through one ledger with a ceiling in CNY, priced at the provider's peak rates without cache
discount. A request that could exceed the ceiling is refused before it is sent, a response without usable usage
stops the run, and nothing is retried silently. Results append per question and resume.

    python evaluations/locomo/consolidation_experiment.py --data locomo10.json --out RUN_DIR \
        --model-cache MODEL_DIR --conversations 1 --ceiling 15
    python evaluations/locomo/consolidation_experiment.py --out RUN_DIR --report
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_recall import evidence_ids, stored_turns, write_cues  # noqa: E402
from run_locomo import (  # noqa: E402
    CATEGORIES,
    Model,
    answer_with_membrain,
    install_model,
    judge,
    log,
    questions,
    sessions,
    start,
    turn_text,
    wait_for_embeddings,
)

ENDPOINT = "https://api.deepseek.com"
ANSWER_MODEL = "deepseek-flash"
TURN_MODEL = "deepseek-flash"
SESSION_MODEL = "deepseek-v4-pro"
# CNY per million tokens at peak hours, cache miss (api-docs.deepseek.com pricing page, read 2026-11-11).
RATES = {"deepseek-flash": (2.0, 8.0), "deepseek-v4-pro": (9.0, 27.0)}
ARMS = ("plain", "turn", "session", "cues")
PRODUCER = "locomo-ingest"
SESSION_OUTPUT_TOKENS = 8000
MAX_SESSION_NOTES = 14

CONSOLIDATION_RULES = """You keep the long-term notes of a memory system. You are given the notes kept so far \
about the people in a conversation, and one finished session of that conversation. Update the notes so that someone \
who reads only the notes knows the lasting facts.

Keep: who each person is and the people in their life; work and studies; what they do regularly (hobbies, sports, \
classes, volunteering); what they like, dislike and care about; health and constraints; where they live, come from \
and have been; plans, and whether they happened; important events with their dates; promises.

Rules:
1. One note per person and topic. When the session adds to a topic that already has a note, write the merged note \
and list the old note's id in "replaces", so lists grow in one place (for example one note listing every activity a \
person does, one listing the places they have camped). Do not add a second note on the same topic.
2. Each note is one or two plain sentences, at most 280 characters, and starts with the person's name.
3. Use absolute dates: turn "last week" or "yesterday" into a date using the session's date.
4. Only what the session says. A plan stays a plan until a session says it happened. Do not add feelings, causes or \
traits that nobody stated.
5. For every note list the ids of the turns it rests on in "sources" (the ids in square brackets). A merged note \
lists the new turns; the turns of the note it replaces stay linked to it.
6. Leave out greetings, small talk and anything that will not matter in a month.

Return JSON: {"notes": [{"text": "...", "kind": "person|preference|plan|routine|milestone|relationship|other", \
"about": "name of the person", "replaces": ["note id"], "sources": ["turn id"]}]}. Return {"notes": []} when the \
session adds nothing lasting. At most """ + str(MAX_SESSION_NOTES) + " notes."


class BudgetStop(RuntimeError):
    pass


class Ledger:
    """Spending in CNY for one run directory; persisted after every request."""

    def __init__(self, path: Path, ceiling: float):
        self.path = path
        if path.exists():
            self.state = json.loads(path.read_text(encoding="utf-8"))
            self.state["ceiling_cny"] = max(self.state["ceiling_cny"], ceiling)
        else:
            self.state = {"ceiling_cny": ceiling, "spent_cny": 0.0, "stopped": None, "models": {}, "phases": {}}
        self.phase = "setup"
        self._save()

    def _save(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)

    def reserve(self, model: str, request_bytes: int, max_output: int) -> float:
        if self.state["stopped"]:
            raise BudgetStop("The run is stopped: " + self.state["stopped"])
        rate_in, rate_out = RATES[model]
        # A token is at least one byte of the request body, so the body's size bounds the input tokens.
        reserve = request_bytes * rate_in / 1e6 + max_output * rate_out / 1e6
        if self.state["spent_cny"] + reserve > self.state["ceiling_cny"]:
            self.stop("ceiling reached before a request")
            raise BudgetStop("The spending ceiling would be exceeded.")
        return reserve

    def settle(self, model: str, reserve: float, usage: dict | None, *, unknown: bool = False):
        entry = self.state["models"].setdefault(model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                                                        "cny": 0.0, "unknown": 0, "errors": 0})
        phase = self.state["phases"].setdefault(self.phase, {"calls": 0, "cny": 0.0})
        entry["calls"] += 1
        phase["calls"] += 1
        prompt, completion = (usage or {}).get("prompt_tokens"), (usage or {}).get("completion_tokens")
        if unknown or type(prompt) is not int or type(completion) is not int:
            cost = reserve  # What it may have cost; the run stops so that this cannot repeat.
            entry["unknown"] += 1
            self.state["stopped"] = "a request ended without usable usage accounting"
        else:
            rate_in, rate_out = RATES[model]
            cost = prompt * rate_in / 1e6 + completion * rate_out / 1e6
            entry["prompt_tokens"] += prompt
            entry["completion_tokens"] += completion
        entry["cny"] = round(entry["cny"] + cost, 6)
        phase["cny"] = round(phase["cny"] + cost, 6)
        self.state["spent_cny"] = round(self.state["spent_cny"] + cost, 6)
        self._save()

    def error(self, model: str):
        self.state["models"].setdefault(model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                                                "cny": 0.0, "unknown": 0, "errors": 0})["errors"] += 1
        self._save()

    def stop(self, reason: str):
        self.state["stopped"] = self.state["stopped"] or reason
        self._save()


class MeteredTransport(httpx.BaseTransport):
    """Counts every chat-completion request against the ledger before and after it is sent."""

    def __init__(self, ledger: Ledger):
        self.ledger, self.inner = ledger, httpx.HTTPTransport(retries=0)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != "api.deepseek.com" or not request.url.path.endswith("/chat/completions"):
            raise BudgetStop("Only the frozen chat-completions endpoint may be called.")
        body = json.loads(request.content)
        model, limit = body["model"], body.get("max_tokens")
        if model not in RATES or type(limit) is not int or not 0 < limit <= 16000 or body.get("stream"):
            raise BudgetStop("A request outside the frozen models and output limits was refused.")
        reserve = self.ledger.reserve(model, len(request.content), limit)
        try:
            response = self.inner.handle_request(request)
            content = response.read()
            response.close()
        except Exception:
            self.ledger.settle(model, reserve, None, unknown=True)
            raise
        if response.status_code != 200:
            self.ledger.error(model)  # The provider bills completed requests; a refusal has no usage.
        else:
            try:
                usage = json.loads(content).get("usage")
            except ValueError:
                usage = None
            self.ledger.settle(model, reserve, usage if isinstance(usage, dict) else None)
        headers = [(key, value) for key, value in response.headers.items()
                   if key.lower() not in ("content-encoding", "content-length", "transfer-encoding")]
        return httpx.Response(response.status_code, headers=headers, content=content, request=request)


def read_key() -> str:
    """The key from the environment, or from the repository's git-ignored .env; never printed or stored."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    path = Path(__file__).resolve().parents[2] / ".env"
    if not key and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "DEEPSEEK_API_KEY":
                key = value.strip().strip("'\"")
    if not key:
        raise SystemExit("Set DEEPSEEK_API_KEY in the environment or in the repository's .env file.")
    os.environ["DEEPSEEK_API_KEY"] = key
    return key


def source(session: str, turn: dict, date: str) -> dict:
    from membrain import host

    record = host.message_record(session, "user", turn_text(date, turn), turn_id=turn["dia_id"], producer=PRODUCER)
    return {"producer_ref": PRODUCER, "source_event_key": record["source_event_key"], "source_revision": 1}


def consolidate(client, model: Model, sample: dict, number: int, date: str, turns: list[dict]) -> dict:
    """One consolidation call for a finished session; returns counts of what was saved or refused."""
    from membrain.notes import KINDS, NoteValidationError, list_notes, save_note

    current = list_notes(client)["items"]
    notes = "\n".join(f"(id: {item['event_id']}) {item['text']}" for item in reversed(current)) or "(none yet)"
    transcript = "\n".join(f"[{turn['dia_id']}] {turn['speaker']}: {turn.get('text', '')}"
                           + (f" [shares an image: {turn['blip_caption']}]" if turn.get("blip_caption") else "")
                           for turn in turns)
    message = model.chat(
        [{"role": "system", "content": CONSOLIDATION_RULES},
         {"role": "user", "content": f"Notes so far:\n{notes}\n\nSession {number}, {date}:\n{transcript}"}],
        json_mode=True, max_tokens=SESSION_OUTPUT_TOKENS)
    outcome = {"proposed": 0, "saved": 0, "replaced": 0, "refused": 0, "unreadable": 0}
    try:
        proposed = json.loads(message.get("content") or "{}").get("notes") or []
    except (ValueError, AttributeError):
        outcome["unreadable"] = 1
        return outcome
    session = f"locomo-{sample['sample_id']}-s{number}"
    by_id = {turn["dia_id"]: turn for turn in turns}
    live = {item["event_id"] for item in current}
    for item in proposed[:MAX_SESSION_NOTES] if isinstance(proposed, list) else []:
        if not isinstance(item, dict) or not str(item.get("text") or "").strip():
            continue
        outcome["proposed"] += 1
        replaces = tuple(value for value in item.get("replaces") or () if value in live)
        refs = [source(session, by_id[value], date) for value in item.get("sources") or () if value in by_id]
        fields = {"kind": item.get("kind") if item.get("kind") in KINDS else "other"}
        if isinstance(item.get("about"), str) and item["about"].strip():
            fields["about"] = item["about"].strip()[:60]
        try:
            saved = save_note(client, str(item["text"]).strip(), replaces=replaces, source_messages=refs, **fields)
        except NoteValidationError:
            outcome["refused"] += 1
            continue
        if saved.get("note_id"):
            outcome["saved"] += 1
            outcome["replaced"] += len(replaces)
            live.difference_update(replaces)
            live.add(saved["note_id"])
        else:
            outcome["refused"] += 1
    return outcome


def prepare(sample: dict, directory: Path, arm: str, cache: Path, ledger: Ledger, transport, ports,
            cues: Path | None = None) -> dict:
    """Store one conversation for one arm, with that arm's consolidation; resumable per session."""
    from membrain import host
    from membrain.extraction import Extractor, extract_turn
    from membrain.notes import list_notes

    marker = directory / "prepared.json"
    if marker.exists():
        start(directory)
        return json.loads(marker.read_text(encoding="utf-8"))
    if ports and not (directory / "profile.json").exists():
        from membrain.embedded_database import default_engine
        from membrain.local_profile import ensure_profile

        ensure_profile(directory, api_port=ports[0], database_port=ports[1], database_engine=default_engine())
    host.ensure_installation(directory)
    install_model(directory, cache)
    start(directory)
    progress_path = directory / "sessions-done.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}
    extractor = Extractor(ENDPOINT, TURN_MODEL, os.environ["DEEPSEEK_API_KEY"], transport=transport) \
        if arm == "turn" else None
    writer = Model(ENDPOINT, SESSION_MODEL, cap=200, thinking=True) if arm == "session" else None
    if writer is not None:
        writer.http = httpx.Client(timeout=600, transport=transport)
    ledger.phase = f"consolidate:{arm}"
    with host.ready_client(directory) as client:
        for number, date, turns in sessions(sample):
            if str(number) in progress:
                continue
            session = f"locomo-{sample['sample_id']}-s{number}"
            outcome = {"turns": 0}
            for turn in turns:
                record = host.message_record(session, "user", turn_text(date, turn), turn_id=turn["dia_id"],
                                             producer=PRODUCER)
                outcome["turns"] += host.deliver(directory, client, record)
                if extractor is not None:
                    try:
                        saved = extract_turn(directory, extractor, None, sources=[source(session, turn, date)],
                                             recording={"revision": 0, "target": None}, session=session)
                        outcome["saved"] = outcome.get("saved", 0) + len(saved)
                    except httpx.HTTPError as error:
                        outcome["errors"] = outcome.get("errors", 0) + 1
                        log("extraction error", turn["dia_id"], type(error).__name__)
            if writer is not None:
                outcome.update(consolidate(client, writer, sample, number, date, turns))
            progress[str(number)] = outcome
            progress_path.write_text(json.dumps(progress, indent=1), encoding="utf-8")
            log(arm, sample["sample_id"], "session", number, outcome)
        notes = list_notes(client)["items"]
    host.pause(directory)  # Questions must never become memories.
    wait_for_embeddings(directory)
    summary = {"arm": arm, "sessions": progress, "notes": len(notes),
               "note_characters": sum(len(item["text"]) for item in notes)}
    if arm == "cues":
        written = json.loads((cues / f"cues-{sample['sample_id']}.json").read_text(encoding="utf-8"))["cues"]
        summary["cues"] = write_cues(sample, directory, written)
        if summary["cues"]["embedded"] != summary["cues"]["written"] or not summary["cues"]["written"]:
            raise SystemExit(f"Cues were not all written and embedded: {summary['cues']}")
    marker.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def run(args) -> None:
    from membrain import desktop

    read_key()
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    selected = [data[int(index)] for index in args.conversations.split(",")]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(out / "ledger.json", args.ceiling)
    transport = MeteredTransport(ledger)
    answerer = Model(ENDPOINT, ANSWER_MODEL, cap=100000)
    answerer.http = httpx.Client(timeout=300, transport=transport)
    ports = tuple(map(int, args.ports.split(","))) if args.ports else None
    for arm_index, arm in enumerate(args.arms.split(",")):
        if arm not in ARMS:
            raise SystemExit(f"Unknown arm {arm}.")
        if arm == "cues" and not args.cues:
            raise SystemExit("The cues arm needs --cues.")
        path = out / f"answers-{arm}.jsonl"
        done = {json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines()} if path.exists() else set()
        for position, sample in enumerate(selected):
            todo = [(qid, qa) for qid, qa in questions(sample, {1, 2, 3, 4}) if qid not in done]
            if args.max_questions:
                todo = todo[:args.max_questions]
            if not todo:
                continue
            directory = out / f"{arm}-{sample['sample_id']}"
            own = (ports[0] + 10 * (arm_index * 10 + position), ports[1] + 10 * (arm_index * 10 + position)) if ports else None
            try:
                summary = prepare(sample, directory, arm, Path(args.model_cache), ledger, transport, own,
                                  Path(args.cues) if args.cues else None)
                log("prepared", arm, sample["sample_id"], "notes", summary["notes"], "chars", summary["note_characters"])
                turns = stored_turns(sample)
                ledger.phase = f"answer:{arm}"
                for qid, qa in todo:
                    started = time.monotonic()
                    result = answer_with_membrain(answerer, sample, directory, qid, qa["question"])
                    verdict = judge(answerer, qa["question"], qa["answer"], result["answer"])
                    row = {"id": qid, "arm": arm, "category": qa["category"], "evidence": len(evidence_ids(qa, turns)),
                           "question": qa["question"], "gold": qa["answer"], **result, **verdict,
                           "seconds": round(time.monotonic() - started, 2)}
                    with path.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            finally:
                try:
                    desktop.stop(directory)
                except desktop.DesktopError:
                    pass
            log("answered", arm, sample["sample_id"], len(todo), "spent", ledger.state["spent_cny"])


def report(args) -> None:
    out = Path(args.out)
    rows = {}
    for arm in (*ARMS, "full"):  # ``full`` is written by full_context_control.py.
        path = out / f"answers-{arm}.jsonl"
        if path.exists():
            rows[arm] = {row["id"]: row for row in map(json.loads, path.read_text(encoding="utf-8").splitlines())}
    shared = set.intersection(*(set(values) for values in rows.values())) if rows else set()
    if args.only:
        rows = {arm: values for arm, values in rows.items() if arm in args.only.split(",")}
        shared = set.intersection(*(set(values) for values in rows.values())) if rows else set()
    if args.conversations_filter:
        wanted = tuple(args.conversations_filter.split(","))
        shared = {item for item in shared if item.rsplit("-q", 1)[0] in wanted}

    def rate(items):
        return f"{sum(row['correct'] for row in items) / len(items):6.1%} ({len(items)})" if items else "   n/a"

    print(f"questions answered by every arm: {len(shared)}")
    print(f"{'':26}" + "".join(f"{arm:>16}" for arm in rows))
    groups = [("all", lambda row: True)] + [(name, lambda row, c=category: row["category"] == c)
                                           for category, name in CATEGORIES.items()]
    groups += [("one evidence turn", lambda row: row["evidence"] == 1),
               ("several evidence turns", lambda row: row["evidence"] > 1)]
    for name, keep in groups:
        print(f"{name:26}" + "".join(f"{rate([values[i] for i in shared if keep(values[i])]):>16}"
                                     for values in rows.values()))
    print(f"{'mean context characters':26}" + "".join(
        f"{round(statistics.fmean(values[i]['context_characters'] for i in shared)) if shared else 0:>16}"
        for values in rows.values()))
    print(f"{'questions with a search':26}" + "".join(
        f"{sum(bool(values[i]['searches']) for i in shared):>16}" for values in rows.values()))
    for first, second in (("plain", "session"), ("plain", "turn"), ("turn", "session"), ("full", "plain"),
                          ("plain", "cues")):
        if first in rows and second in rows:
            gained = sum(rows[second][i]["correct"] and not rows[first][i]["correct"] for i in shared)
            lost = sum(rows[first][i]["correct"] and not rows[second][i]["correct"] for i in shared)
            print(f"{first} -> {second}: gained {gained}, lost {lost}")
            several = [i for i in shared if rows[first][i]["evidence"] > 1]
            print(f"  several evidence turns: gained "
                  f"{sum(rows[second][i]['correct'] and not rows[first][i]['correct'] for i in several)}, lost "
                  f"{sum(rows[first][i]['correct'] and not rows[second][i]['correct'] for i in several)}")
    ledger = out / "ledger.json"
    if ledger.exists():
        state = json.loads(ledger.read_text(encoding="utf-8"))
        print("spent CNY:", state["spent_cny"], "of", state["ceiling_cny"], "| stopped:", state["stopped"])
        for name, phase in state["phases"].items():
            print(f"  {name:22} calls {phase['calls']:>6}  CNY {phase['cny']:.3f}")
        for name, model in state["models"].items():
            print(f"  {name:22} calls {model['calls']:>6}  in {model['prompt_tokens']:>10}  out {model['completion_tokens']:>9}"
                  f"  unknown {model['unknown']}  errors {model['errors']}")
    for arm in rows:
        for marker in sorted(out.glob(f"{arm}-*/prepared.json")):
            summary = json.loads(marker.read_text(encoding="utf-8"))
            print(f"  {marker.parent.name}: {summary['notes']} notes, {summary['note_characters']} characters")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", help="locomo10.json from snap-research/locomo")
    parser.add_argument("--out", required=True)
    parser.add_argument("--model-cache", default="", help="Directory holding the pinned embedding model")
    parser.add_argument("--conversations", default="0,1,2", help="Comma-separated indexes")
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--max-questions", type=int, default=0, help="Per conversation and arm; 0 means all")
    parser.add_argument("--ceiling", type=float, default=0.0, help="Spending ceiling in CNY for this run directory")
    parser.add_argument("--ports", default="", help="API and database ports for new installations, e.g. 8891,55601")
    parser.add_argument("--cues", default="", help="Directory of cues-<conversation>.json files for the cues arm")
    parser.add_argument("--report", action="store_true", help="Only summarize existing results")
    parser.add_argument("--only", default="", help="Report: compare only these arms, e.g. plain,full")
    parser.add_argument("--conversations-filter", default="", help="Report: only these sample ids, e.g. conv-26,conv-30")
    args = parser.parse_args()
    if not args.report:
        if not args.data or not args.model_cache or args.ceiling <= 0:
            parser.error("--data, --model-cache and a positive --ceiling are required to run")
        run(args)
    report(args)


if __name__ == "__main__":
    main()
