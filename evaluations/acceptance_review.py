"""Review pipeline for the final behavioral acceptance (frozen by hash in the attempt plan).

  split   SHEET VERDICTS BLIND_DIR SCENARIO OUT_DIR   one file per case for the second review; refuses to write a
                                                      case file unless every reply appears in it in full
  tally   REVIEW_DIR BLIND_DIR SCENARIO KEY           final scores per arm, literal and with written resolutions
  attribution-inputs REVIEW_DIR BLIND_DIR SCENARIO KEY OUT_DIR   one arm-blind file per gated reply with a standing
                                                      critical error, for attribute.md
  validity RUN_DIR...                                 refuse an attempt whose runs degraded
  r5-inputs REVIEW_DIR BLIND_DIR SCENARIO KEY OUT_DIR   after the re-checks: one arm-blind file per reply with a
                                                      candidate type 4 mark, with that reply's own earlier
                                                      assistant replies, for rule R5 (assistant-claims.md)
  r5-check INPUT_DIR ANSWER_DIR RESULT_DIR             validate both R5 checkers' answers (an invalid one is set
                                                      aside to be redone once), then write each reply's result
  actions-digest REVIEW_DIR BLIND_DIR SCENARIO KEY RUN_DIR...   C5, for RC2, resolution stage only: what each page
                                                      action before a case actually removed in the world of each
                                                      reply with a candidate type 8 mark, by label (actions-KEY.json)
  verdicts VERDICTS SCENARIO                          check a first review before the split; rename prefix keys
                                                      ("L01") to case ids, keeping the original as .raw.json
  diagnose RUN_DIR...                                 for an invalid attempt: where each arm stopped, harness
                                                      event kinds with counts and positions, and error counts by
                                                      exception class; never a message, payload or log line
  gate REVIEW_DIR KEY...                              the attempt-3 pass rule from tallies and attributions

verdicts, tally and gate accept --companion for C5 (critical types 1–9). C5 writes gate-c5.json and never writes
an R4 result. Standing boundary/deletion errors (types 7/8) fail C5 regardless of attribution.
tally and gate accept --manifest PATH, the frozen attempt manifest (load_manifest): a tally then must be of a scenario
file in its gate's pair with the manifest's hash, and gate R4 (or C5) needs exactly that pair's keys, each tally made
with that manifest. Every tally records its scenario's key, file stem and sha256.
A failed gate, R4 or C5, writes its report (gate.json or gate-c5.json) and then exits nonzero.

Final score of a reply: 0 when a critical error stands, otherwise the first reviewer's score_ignoring_critical.
A mark stands when the first reviewer made it and the second confirmed it, or the second added it; written
resolutions (resolution-KEY.json, made before unsealing by the resolution reviewer) then add or remove marks.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path, PurePosixPath


def load(path: str):
    spec = importlib.util.spec_from_file_location("scenario", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_marks(value, maximum):
    return isinstance(value, list) and all(type(mark) is int and 1 <= mark <= maximum for mark in value)


# The frozen attempt manifest -------------------------------------------------------------------------------------------

class ManifestError(ValueError):
    """A frozen attempt manifest that is not valid."""


GATES = ("R4", "C5")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _repo_path(value) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    parts = PurePosixPath(value).parts
    return not PurePosixPath(value).is_absolute() and all(part not in ("", ".", "..") for part in parts) \
        and "/".join(parts) == value


def load_manifest(path) -> dict:
    """Load and validate a frozen attempt manifest; return it as parsed. Raises ManifestError (a ValueError).

    {"version": 1, "attempt_id": "...", "files": {"<repo-relative path>": "<sha256>"},
     "pairs": [{"gate": "R4" | "C5", "scenarios": [{"key": "<key>", "path": "<repo-relative .py>", "sha256": "..."}]}],
     "order": ["<key>", ...]}

    Exactly these fields. Each gate names at most one pair; scenario keys, paths and file stems are unique; every
    order key is in exactly one pair and every pair key is in the order once; a scenario path listed in "files" has
    the same hash there. Hashes are lowercase hex SHA-256. It checks structure only, not the files on disk."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        raise ManifestError(f"invalid manifest: not readable JSON ({error})") from error
    if not isinstance(data, dict) or set(data) != {"version", "attempt_id", "files", "pairs", "order"}:
        raise ManifestError("invalid manifest: expected exactly version, attempt_id, files, pairs and order")
    if type(data["version"]) is not int or data["version"] != 1:
        raise ManifestError("invalid manifest: version must be 1")
    if not isinstance(data["attempt_id"], str) or not data["attempt_id"].strip():
        raise ManifestError("invalid manifest: attempt_id must be a non-empty string")
    files = data["files"]
    if not isinstance(files, dict) or any(not _repo_path(name) or not isinstance(digest, str)
                                          or not _SHA256.fullmatch(digest) for name, digest in files.items()):
        raise ManifestError("invalid manifest: files must map repo-relative paths to sha256 hashes")
    pairs = data["pairs"]
    if not isinstance(pairs, list) or not pairs:
        raise ManifestError("invalid manifest: pairs must be a non-empty list")
    keys, paths, stems, gates = [], set(), set(), set()
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != {"gate", "scenarios"} or pair["gate"] not in GATES:
            raise ManifestError("invalid manifest: each pair has exactly a gate (R4 or C5) and scenarios")
        if pair["gate"] in gates:
            raise ManifestError(f"invalid manifest: more than one {pair['gate']} pair")
        gates.add(pair["gate"])
        if not isinstance(pair["scenarios"], list) or not pair["scenarios"]:
            raise ManifestError(f"invalid manifest: the {pair['gate']} pair has no scenarios")
        for scenario in pair["scenarios"]:
            if (not isinstance(scenario, dict) or set(scenario) != {"key", "path", "sha256"}
                    or not isinstance(scenario["key"], str) or not _KEY.fullmatch(scenario["key"])
                    or not _repo_path(scenario["path"]) or not scenario["path"].endswith(".py")
                    or not isinstance(scenario["sha256"], str) or not _SHA256.fullmatch(scenario["sha256"])):
                raise ManifestError("invalid manifest: each scenario has exactly a key, a repo-relative .py path "
                                    "and a sha256")
            stem = PurePosixPath(scenario["path"]).stem
            if scenario["key"] in keys or scenario["path"] in paths or stem in stems:
                raise ManifestError("invalid manifest: scenario keys, paths and file stems must be unique")
            if scenario["path"] in files and files[scenario["path"]] != scenario["sha256"]:
                raise ManifestError("invalid manifest: a scenario's hash differs from its entry in files")
            keys.append(scenario["key"])
            paths.add(scenario["path"])
            stems.add(stem)
    order = data["order"]
    if (not isinstance(order, list) or any(not isinstance(key, str) for key in order)
            or len(order) != len(set(order)) or set(order) != set(keys)):
        raise ManifestError("invalid manifest: order must list every scenario key exactly once")
    return data


def manifest_scenarios(manifest: dict, gate_name: str) -> list[dict]:
    """The scenarios of a validated manifest's pair for one gate ([] when it has no such pair)."""
    return next((pair["scenarios"] for pair in manifest["pairs"] if pair["gate"] == gate_name), [])


def _manifest(path) -> tuple[dict, str]:
    """A validated manifest and its file's sha256, for the commands; a problem stops the command."""
    try:
        return load_manifest(path), sha256_file(path)
    except ManifestError as error:
        raise SystemExit(str(error)) from error


def replies(blind_dir: Path, module, scenario: str) -> dict:
    """(case, label) -> reply text, from the results the blinded sheet was built from."""
    sealed = json.loads((blind_dir / f"sealed_{scenario}.json").read_text())
    rows = {}
    for path in blind_dir.glob(f"results_{scenario}_*.jsonl"):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            rows[(row["arm"], row["session"], row["turn"])] = row
    found = {}
    for session, turn, case, _criteria in module.CASES:
        for label, arm in sealed[case].items():
            found[(case, label)] = rows[(arm, session, turn)]["reply"] or "(no reply)"
    return found


def split(sheet: Path, verdicts: Path, blind_dir: Path, scenario_path: str, out: Path) -> None:
    module = load(scenario_path)
    scenario = Path(scenario_path).stem
    text, marks = sheet.read_text(), json.loads(verdicts.read_text())
    cases = [case for _, _, case, _ in module.CASES]
    starts = sorted((m.start(), m.group(1)) for m in re.finditer(r"(?m)^## (\S+)\n", text) if m.group(1) in cases)
    if [case for _, case in starts] != cases:
        raise SystemExit("case headings missing or out of order in the sheet")
    truth = text[text.index("## Ground truth"):starts[0][0]]
    full = replies(blind_dir, module, scenario)
    out.mkdir(parents=True, exist_ok=True)
    for index, (start, case) in enumerate(starts):
        body = text[start:starts[index + 1][0] if index + 1 < len(starts) else len(text)]
        for label in "ABC":
            if body.count(f"\n### {label}\n") != 1 or full[(case, label)].strip() not in body:
                raise SystemExit(f"{case}: reply {label} is not complete in its case file")
        first = {label: {"critical": verdict.get("critical", []), "conditions": verdict.get("conditions", [])}
                 for label, verdict in marks[case].items()}
        (out / f"{case}.md").write_text(truth + body + "\n\n## First reviewer's critical-error marks\n\n"
                                        + json.dumps(first, ensure_ascii=False) + "\n")
        print(case, "ok")


def r5_inputs(review: Path, blind_dir: Path, scenario_path: str, key: str, out: Path) -> None:
    """One file per reply with a candidate type 4 mark, for rule R5 (claims about what the assistant itself said).

    Each file holds the ground truth, the case and that reply only, both reviewers' marks and evidence for it, and
    that reply's own earlier assistant replies with the user message each answered, oldest first, up to the case's
    message. It names the reply by case prefix and label, never by arm."""
    module = load(scenario_path)
    scenario = Path(scenario_path).stem
    sealed = json.loads((blind_dir / f"sealed_{scenario}.json").read_text())
    rows = {}
    for path in blind_dir.glob(f"results_{scenario}_*.jsonl"):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            rows[(row["arm"], row["session"], row["turn"])] = row
    turns = {session: messages for session, messages in module.SESSIONS_LONG}
    order = [(session, index) for session, messages in module.SESSIONS_LONG for index in range(len(messages))]
    first = json.loads((review / f"verdicts-{key}.json").read_text())
    if out.exists():
        raise SystemExit(f"{out} exists: R5 inputs are written once, into a new folder")
    files = {}
    for session, turn, case, _criteria in module.CASES:
        case_text = (review / f"recheck-{key}" / f"{case}.md").read_text()
        second = json.loads((review / f"recheck-{key}" / f"{case}.json").read_text())
        head = case_text[:case_text.index("\n### A\n")]
        for label, arm in sealed[case].items():
            mine, theirs = first[case].get(label, {}), second.get(label, {})
            if 4 not in set(mine.get("critical", [])) | set(theirs.get("critical", [])) | set(theirs.get("added", [])):
                continue
            body = case_text[case_text.index(f"\n### {label}\n"):]
            following = [body.find(f"\n### {other}\n", 1) for other in "ABC" if other != label]
            ends = [index for index in following + [body.find("\n## First reviewer", 1)] if index > 0]
            reply = body[:min(ends)] if ends else body
            lines = [head.rstrip(), reply.rstrip(), "", "## The reviewers' marks on this reply", "",
                     "First reviewer: " + json.dumps({k: mine.get(k) for k in ("critical", "conditions", "reason")},
                                                     ensure_ascii=False),
                     "Second reviewer: " + json.dumps(theirs, ensure_ascii=False), "",
                     "## This reply's own earlier assistant replies, oldest first", ""]
            for earlier_session, earlier_turn in order[:order.index((session, turn))]:
                row = rows.get((arm, earlier_session, earlier_turn))
                if row is None:
                    raise SystemExit(f"{case.split('-')[0]}/{label}: a turn before the case is missing from the results")
                lines += [f"### {row['date']} · {earlier_session}, message {earlier_turn + 1}", "",
                          "User: " + turns[earlier_session][earlier_turn], "",
                          "Assistant: " + ((row.get("reply") or "").strip() or "(no reply)"), ""]
            files[f"{case.split('-')[0]}-{label}.md"] = "\n".join(lines)
    out.mkdir(parents=True)  # Only once every file is ready: a failure leaves no partial folder.
    for name, text in files.items():
        (out / name).write_text(text)
    print(json.dumps(sorted(files)))


_ENTRY = re.compile(r"(?m)^### (\d{4}-\d{2}-\d{2}) · (\S+), message (\d+)$")


def _r5_problem(answer, entries: set) -> str | None:
    """Why one R5 checker's answer is invalid, or None."""
    if not isinstance(answer, dict) or not isinstance(answer.get("claims"), list) or not answer["claims"]:
        return "no claims"
    for claim in answer["claims"]:
        if not isinstance(claim, dict) or claim.get("kind") not in ("assistant_speech", "adopted", "user_fact"):
            return "a claim has no valid kind"
        if claim["kind"] == "assistant_speech" and not isinstance(claim.get("supported"), bool):
            return "an assistant_speech claim has no boolean supported"
        if claim["kind"] != "assistant_speech" and claim.get("supported") is not None:
            return "only assistant_speech claims can be supported"
        if claim.get("supported") is True:
            match = _ENTRY.fullmatch("### " + str(claim.get("entry", "")).strip())
            if not match or match.group(0) not in entries or match.group(2).startswith("roleplay-"):
                return "a supported claim does not name a real-life entry of the file"
    cleared = all(claim["kind"] == "assistant_speech" and claim["supported"] is True for claim in answer["claims"])
    if answer.get("type4_cleared") is not cleared:
        return "type4_cleared does not follow from the claims"
    return None


def r5_check(inputs: Path, outputs: Path, results: Path) -> None:
    """Validate both R5 checkers' answers for every input; set an invalid answer aside as .rejected (it is redone
    once); write each reply's result for resolution: cleared only when both answers are valid and both clear it."""
    redo, final = [], {}
    for source in sorted(inputs.glob("*.md")):
        entries = {match.group(0) for match in _ENTRY.finditer(source.read_text())}
        cleared = True
        for checker in ("1", "2"):
            answer_path = outputs / f"{source.stem}.{checker}.json"
            rejected = outputs / f"{source.stem}.{checker}.rejected.json"
            try:
                problem = _r5_problem(json.loads(answer_path.read_text()), entries)
            except (OSError, ValueError):
                problem = "missing or not JSON"
            if problem and not rejected.exists():
                if answer_path.exists():
                    answer_path.rename(rejected)
                redo.append(f"{source.stem}.{checker}: {problem}")
            cleared = cleared and problem is None and json.loads(answer_path.read_text())["type4_cleared"]
        final[source.stem] = cleared
    if redo:
        print(json.dumps({"redo": redo}))
        return
    results.mkdir(parents=True, exist_ok=True)
    for name, cleared in final.items():
        (results / f"{name}.json").write_text(json.dumps({"type4_cleared": cleared}))
    print(json.dumps({"results": final}))


# Record kinds other than messages a page action can remove, read from the page's counts before and after it. The
# harness does not record which earlier messages those records came from, so the digest names only their kinds.
_RECORD_KINDS = ("notes", "feelings", "shared_moments")

DIGEST_DISCLOSURE = (
    "For the resolution reviewer only, after every first and second review is final; for rule RC2 (type 8). No earlier "
    "stage reads it. It names no assistant: replies are keyed by case and label through the sealed mapping.")
DIGEST_LIMITATIONS = [
    "Removed messages are given by scenario position (session index, message number, role). For notes, feelings, "
    "shared moments and familiarity only the kind removed is given: the run does not record which messages those "
    "records came from. The conversation itself stays unless a message is listed as removed.",
    "A reply whose world held no record of a kind shows none removed. Where other replies of the same case show such "
    "a removal, that difference can suggest which assistant wrote the reply. It is kept because RC2 needs to know "
    "whether the record was removed in this reply's world; nothing beyond the removal itself is shown.",
]


def _applies(action: dict, arm: str) -> bool:
    """Whether the harness applies a scenario page action in this arm (F follows P, as in c5-harness.py)."""
    return not action.get("arms") or ("P" if arm == "F" else arm) in action["arms"]


def _digest_outcome(record: dict, arm: str, sessions: list) -> dict:
    """What one recorded page action actually removed in one arm: removed message positions (session index, message
    number, role) and the other record kinds it removed. No counts, and nothing else of the record (its detail,
    topics, labels, mood, state or time)."""
    result = record.get("result")
    if not isinstance(result, dict) or result.get("failed"):
        raise SystemExit("a page action failed or has no result: the run is invalid and is not scored")
    removed = []
    for entry in result.get("removed", []):
        if (not isinstance(entry, list) or len(entry) != 3 or not isinstance(entry[0], str)
                or entry[0] not in sessions or type(entry[1]) is not int or entry[1] < 0
                or entry[2] not in ("user", "assistant")):
            raise SystemExit("a page action removed a position that is not one of this scenario's messages")
        removed.append([sessions.index(entry[0]) + 1, entry[1] + 1, entry[2]])
    removed.sort()
    before, after = record.get("before"), record.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise SystemExit("a page action record has no before and after state")
    kinds = []
    if arm == "F":  # The reference history holds only the conversation: it removes messages and nothing else.
        if after.get("removed_still_in_history"):
            raise SystemExit("the reference history kept a message its page action removed")
    else:
        for field in ("messages", *_RECORD_KINDS, "familiarity_days"):
            if type(before.get(field)) is not int or type(after.get(field)) is not int:
                raise SystemExit("a page action record has no count of what it removed")
        if before["messages"] - after["messages"] > len(removed):
            kinds.append("messages without a recorded position")
        kinds += [kind for kind in _RECORD_KINDS if after[kind] < before[kind]]
        if after["familiarity_days"] < before["familiarity_days"] or after.get("familiarity") != before.get("familiarity"):
            kinds.append("familiarity")
    return {"removed_messages": removed, "removed_records": kinds}


def actions_digest(review: Path, blind_dir: Path, scenario_path: str, key: str, run_dirs: list[Path]) -> None:
    """For rule RC2, disclosed only to the resolution stage: what each page action before a case actually removed, in
    the world of each reply with a candidate type 8 mark. Written once to REVIEW/actions-KEY.json, after every first
    and second review is complete and before any resolution exists: {"stage", "disclosure", "limitations",
    "replies": {"<case id>/<label>": ...}}, keyed through the sealed mapping like the resolution file. It names no arm
    and holds only action kinds, positions (session index, message number), removed message positions and the other
    record kinds removed: no counts, state, or message, note, feeling, topic or session text.

    Every arm's page-actions.jsonl must hold exactly the scenario's PAGE_ACTIONS that apply to it, in order, and none
    may have failed. An action that does not apply in a reply's arm removed nothing there."""
    verdicts(review / f"verdicts-{key}.json", scenario_path, companion=True)
    module = load(scenario_path)
    scenario = Path(scenario_path).stem
    out = review / f"actions-{key}.json"
    if out.exists():
        raise SystemExit(f"{out} exists: the actions digest is written once")
    if (review / f"resolution-{key}.json").exists():
        raise SystemExit("a resolution already exists: the actions digest is made for the resolution stage, before it")
    for _session, _turn, case, _criteria in module.CASES:
        try:
            second = json.loads((review / f"recheck-{key}" / f"{case}.json").read_text())
        except (OSError, ValueError):
            second = None
        if not isinstance(second, dict) or set(second) != set("ABC"):
            raise SystemExit("the actions digest is disclosed only after every second review is complete")
    sealed = json.loads((blind_dir / f"sealed_{scenario}.json").read_text())
    first = json.loads((review / f"verdicts-{key}.json").read_text())
    sessions = [session for session, _ in module.SESSIONS_LONG]
    actions = list(getattr(module, "PAGE_ACTIONS", None) or [])
    for session, turn, action in actions:
        if (session not in sessions or type(turn) is not int or not isinstance(action, dict)
                or not isinstance(action.get("do"), str) or not _KIND.fullmatch(action["do"])):
            raise SystemExit("PAGE_ACTIONS has an action without a valid kind and position")
    ordered = sorted(range(len(actions)), key=lambda index: (sessions.index(actions[index][0]), actions[index][1],
                                                             index))
    outcomes: dict[str, dict] = {}
    for run in run_dirs:
        results = list(run.glob(f"results_{scenario}_*.jsonl"))
        rows = [json.loads(line) for line in results[0].read_text().splitlines()] if len(results) == 1 else []
        arms = {row.get("arm") for row in rows}
        if not rows or len(arms) != 1 or {row.get("scenario") for row in rows} != {scenario}:
            raise SystemExit(f"{run.name}: expected one results file of this scenario, from one arm")
        arm = arms.pop()
        if arm in outcomes:
            raise SystemExit("two run directories are the same arm")
        expected = [index for index in ordered if _applies(actions[index][2], arm)]
        log = run / "page-actions.jsonl"
        records = [json.loads(line) for line in log.read_text().splitlines() if line.strip()] if log.exists() else []
        if len(records) != len(expected) or any(
                not isinstance(record, dict) or record.get("session") != actions[index][0]
                or record.get("before_turn") != actions[index][1] or record.get("action") != actions[index][2]["do"]
                for record, index in zip(records, expected)):
            raise SystemExit(f"{run.name}: the recorded page actions are not the scenario's PAGE_ACTIONS")
        outcomes[arm] = {index: _digest_outcome(record, arm, sessions) for record, index in zip(records, expected)}
    if set(outcomes) != {arm for labels in sealed.values() for arm in labels.values()}:
        raise SystemExit("the run directories are not the arms of the sealed mapping")
    nothing = {"removed_messages": [], "removed_records": []}
    digest = {}
    for session, turn, case, _criteria in module.CASES:
        second = json.loads((review / f"recheck-{key}" / f"{case}.json").read_text())
        at = (sessions.index(session), turn)
        for label, arm in sorted(sealed[case].items()):
            mine, theirs = first[case].get(label, {}), second.get(label, {})
            if 8 not in set(mine.get("critical", [])) | set(theirs.get("critical", [])) | set(theirs.get("added", [])):
                continue
            entries = []
            for index in ordered:
                action_session, before_turn, action = actions[index]
                if (sessions.index(action_session), before_turn) > at:
                    continue  # Applied after the case's message.
                entries.append({"action": action["do"], "session": sessions.index(action_session) + 1,
                                "before_message": before_turn + 1, **outcomes[arm].get(index, nothing)})
            digest[f"{case}/{label}"] = {"session": at[0] + 1, "message": turn + 1, "actions": entries}
    out.write_text(json.dumps({"stage": "resolution", "disclosure": DIGEST_DISCLOSURE,
                               "limitations": DIGEST_LIMITATIONS, "replies": digest}, indent=1))
    print(json.dumps(sorted(digest)))


# Resolution rules (C5, and R4 with a frozen manifest): the critical types each may change, and whether it may add a mark as well as remove one.
# R1 to R5 are resolve.md's, RC1 and RC2 companion.md's. Types 6 and 8 change only through RC1 and RC2, types 7 and 9
# only through R3, and R5 clears only type 4 (plan: "It never clears types 6 to 9"). R1 removes only types 2, 3 and 5:
# types 1 and 4 are settled by R2 (and R5), in both directions. Whether an R1 condition is false is the resolution
# reviewer's reading of the scenario order; no artifact records it, so only the condition's existence is checked.
_RULES = {"R1": ({2, 3, 5}, False), "R2": ({1, 3, 4}, True), "R3": ({2, 3, 5, 7, 9}, False),
          "R5": ({4}, False), "RC1": ({6}, True), "RC2": ({8}, True)}


def _resolution_change_problem(review: Path, key: str, case: str, label: str, change: dict, verdict: dict,
                              check: dict, literal: set, digest: dict) -> str | None:
    """Why one resolution change breaks the rules (C5, or R4 bound to a manifest), or None. Every removed or added type carries its rule in
    "rules" ({"<type>": "<rule>"}); the rule must be allowed to change that type in that direction, be named in the
    reason, and rest on its evidence: R1 on a condition the first reviewer recorded for that type, R3 on a mark only
    the second reviewer added, R5 on an R5 result that cleared this reply, RC2 on this reply's actions digest entry.
    A mark is added only when a reviewer made it, except type 3 when R2 re-checks a corrected fact."""
    remove, add = set(change.get("remove", [])), set(change.get("add", []))
    if not remove and not add:
        return None
    rules = change.get("rules")
    if not isinstance(rules, dict) or set(rules) != {str(mark) for mark in remove | add}:
        return 'every removed or added type needs exactly one rule tag in "rules"'
    if remove & add:
        return "a type is both removed and added"
    if remove - literal:
        return "it removes a mark that does not stand literally"
    if add & literal:
        return "it adds a mark that already stands"
    candidates = set(verdict["critical"]) | set(check["critical"]) | set(check["added"])
    for mark in sorted(remove | add):
        rule = rules[str(mark)]
        if not isinstance(rule, str) or rule not in _RULES:
            return f"type {mark} has no known rule tag (R1, R2, R3, R5, RC1 or RC2)"
        types, adds = _RULES[rule]
        if mark not in types:
            return f"{rule} cannot change type {mark}"
        if mark in add and not adds:
            return f"{rule} can only remove a mark, not add type {mark}"
        if not re.search(rf"\b{rule}\b", change["reason"]):
            return f"the reason does not name {rule}"
        if rule == "R2" and mark == 3 and (mark in remove or not candidates & {1, 4}):
            return "R2 only adds type 3, when a candidate type 1 or 4 mark is re-checked as a corrected fact"
        if mark in add and mark not in candidates and not (rule == "R2" and mark == 3):
            return f"type {mark} is added although no reviewer made it"
        if rule == "R1" and not any(isinstance(item, dict) and item.get("type") == mark
                                    for item in verdict.get("conditions") or []):
            return f"R1: the first reviewer recorded no condition for type {mark}"
        if rule == "R3" and mark not in set(check["added"]):
            return "R3 removes only a mark the second reviewer added, never one both reviewers made"
        if rule == "R5":
            result = review / f"r5-{key}" / f"{case.split('-')[0]}-{label}.json"
            try:
                cleared = json.loads(result.read_text())
            except (OSError, ValueError):
                cleared = None
            if not isinstance(cleared, dict) or cleared.get("type4_cleared") is not True:
                return f"R5: r5-{key}/{result.name} does not clear this reply"
        if rule == "RC2" and f"{case}/{label}" not in digest:
            return f"RC2: actions-{key}.json has no entry for this reply"
    return None


def tally(review: Path, blind_dir: Path, scenario_path: str, key: str, *, companion=False,
          manifest: Path | None = None) -> None:
    """Final scores per arm, literal and resolved. The tally records the scenario's key, file stem and sha256; with a
    frozen attempt manifest, the key must be in the pair of this tally's gate and the file must match its entry."""
    scenario = Path(scenario_path).stem
    digest_of_scenario = sha256_file(scenario_path)
    bound = None
    if manifest is not None:
        frozen, frozen_hash = _manifest(manifest)
        gate_name = "C5" if companion else "R4"
        entry = next((item for item in manifest_scenarios(frozen, gate_name) if item["key"] == key), None)
        if entry is None:
            raise SystemExit(f"invalid tally: key {key!r} is not in the manifest's {gate_name} pair")
        if PurePosixPath(entry["path"]).stem != scenario or entry["sha256"] != digest_of_scenario:
            raise SystemExit(f"invalid tally: the scenario file is not the manifest's {key!r} scenario")
        bound = {"attempt_id": frozen["attempt_id"], "sha256": frozen_hash}
    verdicts(review / f"verdicts-{key}.json", scenario_path, companion=companion)
    module = load(scenario_path)
    sealed = json.loads((blind_dir / f"sealed_{scenario}.json").read_text())
    first = json.loads((review / f"verdicts-{key}.json").read_text())
    path = review / f"resolution-{key}.json"
    resolution = json.loads(path.read_text()) if path.exists() else {}
    digest = {}
    # C5 tallies, and R4 tallies bound to a frozen manifest, check every resolution change against its rule. A
    # historical R4 tally (no manifest) keeps its untagged resolutions exactly as before.
    strict = companion or bound is not None
    if strict:
        known = {f"{case}/{label}" for case in first for label in first[case]}
        if not isinstance(resolution, dict) or set(resolution) - known:
            raise SystemExit("invalid resolution: every entry must name a reply of this scenario as <case id>/<label>")
    if companion:
        actions = review / f"actions-{key}.json"
        if actions.exists():
            data = json.loads(actions.read_text())
            if not isinstance(data, dict) or data.get("stage") != "resolution" or not isinstance(data.get("replies"),
                                                                                                 dict):
                raise SystemExit(f"invalid actions digest: actions-{key}.json is not made by actions-digest")
            digest = data["replies"]
    totals, rows = {"literal": {}, "resolved": {}}, []
    for _, _, case, _ in module.CASES:
        second = json.loads((review / f"recheck-{key}" / f"{case}.json").read_text())
        if not isinstance(second, dict) or set(second) != set("ABC"):
            raise SystemExit(f"invalid second review: {case} must cover A, B and C")
        for label, verdict in first[case].items():
            arm = sealed[case][label]
            check = second.get(label, {})
            change = resolution.get(f"{case}/{label}", {})
            maximum = 9 if companion else 5
            if (not isinstance(check, dict) or not isinstance(change, dict)
                    or any(not _valid_marks(check.get(field), maximum)
                           for field in ("critical", "confirmed", "rejected", "added"))
                    or not isinstance(check.get("evidence"), str)
                    or any(not _valid_marks(change.get(field, []), maximum) for field in ("remove", "add"))):
                raise SystemExit(f"invalid review marks: {case}/{label}")
            marks = set(verdict["critical"])
            confirmed, rejected, added = (set(check[field]) for field in ("confirmed", "rejected", "added"))
            if (confirmed & rejected or confirmed | rejected != marks or added & marks
                    or set(check["critical"]) != confirmed | added
                    or ((marks or added) and not check["evidence"].strip())
                    or ((change.get("remove") or change.get("add"))
                        and (not isinstance(change.get("reason"), str) or not change["reason"].strip()))):
                raise SystemExit(f"invalid review marks: {case}/{label}")
            literal = (marks & set(check.get("confirmed", []))) | set(check.get("added", []))
            if strict and (problem := _resolution_change_problem(review, key, case, label, change, verdict, check,
                                                                literal, digest)):
                raise SystemExit(f"invalid resolution: {case}/{label}: {problem}")
            resolved = (literal - set(change.get("remove", []))) | set(change.get("add", []))
            base = verdict["score_ignoring_critical"]
            for name, standing in (("literal", literal), ("resolved", resolved)):
                totals[name][arm] = totals[name].get(arm, 0) + (0 if standing else base)
            rows.append({"case": case, "label": label, "arm": arm, "base": base, "literal": sorted(literal),
                         "resolved": sorted(resolved), "reason": change.get("reason")})
    result = {"totals": totals, "rows": rows,
              "scenario": {"key": key, "stem": scenario, "sha256": digest_of_scenario}}
    if companion:
        result["gate"] = "C5"
    if bound:
        result["manifest"] = bound
    (review / f"tally-{key}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print(json.dumps(totals))
    for row in rows:
        if row["base"] < 1 or row["literal"] or row["resolved"]:
            print(row["case"], row["label"], row["arm"], "base", row["base"], "literal", row["literal"],
                  "resolved", row["resolved"], row["reason"] or "")


def _turn_rows(blind_dir: Path, scenario: str, arm: str) -> dict:
    rows = {}
    for line in (blind_dir / f"results_{scenario}_{arm}.jsonl").read_text().splitlines():
        row = json.loads(line)
        rows[(row["session"], row["turn"])] = row
    return rows


def _content(item: dict) -> str:
    text = item.get("content") or ""
    calls = item.get("tool_calls") or []
    if calls:
        text += "".join(f"\n[tool call] {call['function']['name']}({call['function'].get('arguments', '')})"
                        for call in calls)
    return text


def attribution_inputs(review: Path, blind_dir: Path, scenario_path: str, key: str, out: Path,
                       gated: str = "PE") -> None:
    """One file per gated reply with a standing critical error: the marks and evidence, taken from the review files,
    and everything memory gave the host in that session up to and including the scored turn. Files are named by
    case and label only; nothing is written by hand."""
    module = load(scenario_path)
    scenario = Path(scenario_path).stem
    sealed = json.loads((blind_dir / f"sealed_{scenario}.json").read_text())
    tally_rows = json.loads((review / f"tally-{key}.json").read_text())["rows"]
    first = json.loads((review / f"verdicts-{key}.json").read_text())
    path = review / f"resolution-{key}.json"
    resolution = json.loads(path.read_text()) if path.exists() else {}
    out.mkdir(parents=True, exist_ok=True)
    for row in tally_rows:
        if not row["resolved"] or sealed[row["case"]][row["label"]] not in gated:
            continue
        case, label = row["case"], row["label"]
        session, turn = next((s, t) for s, t, c, _ in module.CASES if c == case)
        rows = _turn_rows(blind_dir, scenario, sealed[case][label])
        second = json.loads((review / f"recheck-{key}" / f"{case}.json").read_text()).get(label, {})
        marks = (f"Standing critical error type(s): {row['resolved']}\n\nFirst reviewer: {first[case][label].get('reason', '')}"
                 f"\n\nSecond reviewer: {second.get('evidence', '')}"
                 f"\n\nResolution: {resolution.get(f'{case}/{label}', {}).get('reason', 'none')}")
        earlier = []
        for index in range(turn):
            previous = rows[(session, index)]
            earlier.append(f"## Message {index + 1} of this session\n\n" + "\n\n".join(
                f"[{item['role']}] {_content(item)}" for item in previous["transcript"]))
        current = rows[(session, turn)]
        calls = "\n".join(f"- {call['name']}({json.dumps(call['arguments'], ensure_ascii=False)}) -> {call['result']}"
                          for call in current.get("tool_calls", []))
        (out / f"{case.split('-')[0]}-{label}.md").write_text(
            f"# Critical error\n\n{marks}\n\n# Context at the start of this session (the session-start memory, or "
            f"for hosts without hooks the memory added to the session's first message)\n\n"
            f"{current.get('session_context') or '(none)'}\n\n# Earlier messages in this session, as the assistant saw "
            f"them\n\n{chr(10).join(earlier) or '(none: this is the first message)'}\n\n# The scored message as the "
            f"assistant received it (memory added before the user's text)\n\n{current['host_user_content']}\n\n"
            f"# Memory tool calls in this message\n\n{calls or '(none)'}\n\n# Reply\n\n{current['reply']}\n")
        print(out / f"{case.split('-')[0]}-{label}.md")


def _run(run: Path) -> tuple[list[dict], list[tuple[str, int]], str]:
    """A run directory's result rows, the scenario's turns in order (session, turn) and its log ("" if none)."""
    results = list(run.glob("results_*.jsonl"))
    rows = [json.loads(line) for line in results[0].read_text().splitlines()] if len(results) == 1 else []
    order = []
    if rows:
        scenario = load(str(Path(__file__).parent / (rows[0]["scenario"] + ".py")))
        order = [(session, index) for session, turns in scenario.SESSIONS_LONG for index in range(len(turns))]
    log = (run / "run.log").read_text(errors="replace") if (run / "run.log").exists() else ""
    return rows, order, log


def _position(order: list, row: dict) -> str:
    """Where a turn is, without naming its session (session ids describe content)."""
    key = (row["session"], row["turn"])
    return f"turn {order.index(key) + 1} of {len(order)}" if key in order else "an unknown turn"


def validity(run_dirs: list[Path]) -> dict:
    """Refuse an attempt whose runs degraded: a missing or unfinished log, missing or empty replies, a call cap, a
    harness error or an index timeout in any arm. Names turns by position only. Prints the reference arm's largest
    prompt and each arm's count of retried empty replies."""
    problems, largest, retried = [], 0, {}
    if not run_dirs:
        problems.append("No run directories supplied")
    for run in run_dirs:
        rows, order, log = _run(run)
        if not rows:
            problems.append(f"{run}: expected one results file with rows")
            continue
        arm, scenario = rows[0]["arm"], rows[0]["scenario"]
        if [(row["session"], row["turn"]) for row in rows] != order:
            problems.append(f"{run}: missing, duplicate or out-of-order turns ({len(rows)} of {len(order)} rows)")
        if any(row["arm"] != arm or row["scenario"] != scenario for row in rows):
            problems.append(f"{run}: mixed arm or scenario identities")
        problems += [f"{run}: empty reply at {_position(order, row)}" for row in rows if not row["reply"].strip()]
        lines = [line for line in log.splitlines() if line.strip()]
        if not lines or not lines[-1].endswith(f"{arm} {scenario} finished"):
            problems.append(f"{run}: run.log missing, empty or not ending with the finished line")
        problems += [f"{run}: {marker}" for marker in ("cap reached", "Traceback") if marker in log]
        retried[f"{run.name} ({arm})"] = log.count("host error ValueError empty reply")
        events = run / "harness-events.jsonl"
        if events.exists():
            for number, line in enumerate(events.read_text().splitlines(), 1):
                try:
                    event = json.loads(line)
                    if (not isinstance(event, dict) or not isinstance(event.get("kind"), str)
                            or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", event["kind"])):
                        raise ValueError
                except (ValueError, TypeError):
                    problems.append(f"{run}: malformed harness event at line {number}")
                    continue
                problems.append(f"{run}: harness degradation {event['kind']}")
        if arm == "F":
            largest = max(largest, max(row["usage"].get("prompt_tokens", 0) for row in rows))
    result = {"valid": not problems, "problems": problems, "reference_largest_prompt_tokens": largest,
              "empty_replies_retried": retried}
    print(json.dumps(result))
    return result


_KIND = re.compile(r"[a-z][a-z0-9_]{0,63}")
_EXCEPTION_LINE = re.compile(r"((?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*(?:Error|Exception|Exit|Interrupt|Stop|Timeout))(?::|$)")
# Exception classes a run can raise: Python's own, httpx's and the billing guard's. A name outside this list could be
# text from a multi-line message, so it is printed as "other".
_KNOWN_CLASSES = frozenset(
    {name for name, value in vars(__import__("builtins")).items()
     if isinstance(value, type) and issubclass(value, BaseException)}
    | {"BudgetStop", "JSONDecodeError", "CloseError", "ConnectError", "ConnectTimeout", "CookieConflict",
       "DecodingError", "HTTPError", "HTTPStatusError", "InvalidURL", "LocalProtocolError", "NetworkError",
       "PoolTimeout", "ProtocolError", "ProxyError", "ReadError", "ReadTimeout", "RemoteProtocolError",
       "RequestError", "RequestNotRead", "ResponseNotRead", "StreamClosed", "StreamConsumed", "StreamError",
       "TimeoutException", "TooManyRedirects", "TransportError", "UnsupportedProtocol", "WriteError", "WriteTimeout"})


def _class_name(word: str) -> str:
    """An exception class name from a log line, without any module prefix, or "other" when it is not one a run can
    raise: never any other text."""
    name = word.rstrip(":").rsplit(".", 1)[-1]
    return name if name in _KNOWN_CLASSES else "other"


def _event_position(event: dict, sessions: list) -> str | None:
    """A harness event's position by session index and message number; never the session id (ids describe content)."""
    session, turn = event.get("session"), event.get("turn")
    if not isinstance(session, str) or session not in sessions:
        return None
    where = f"session {sessions.index(session) + 1} of {len(sessions)}"
    return where + (f", message {turn + 1}" if type(turn) is int and turn >= 0 else "")


def diagnose(run_dirs: list[Path]) -> None:
    """What an invalid run's diagnosis may read, per run directory: how far each arm got and its empty replies, by
    position; each harness event's kind, with a count per kind and positions (session index, message) where the event
    has them; and counts of the log's error lines by kind and exception class name. It never prints a payload string,
    a session id, an exception message, a log line or any input, reply, context or transcript: those can carry
    held-out content (attempt 3 lost a scenario that way)."""
    for run in run_dirs:
        rows, order, log = _run(run)
        sessions = list(dict.fromkeys(session for session, _ in order))
        print(f"== {run.name}: {len(rows)} of {len(order)} turns done"
              + (f"; last done {_position(order, rows[-1])}" if rows else ""))
        for row in rows:
            if not str(row.get("reply") or "").strip():
                print(f"   empty reply at {_position(order, row)}")
        kinds: dict[str, list] = {}
        malformed = 0
        events = run / "harness-events.jsonl"
        for line in (events.read_text(errors="replace").splitlines() if events.exists() else []):
            try:
                event = json.loads(line)
            except ValueError:
                event = None
            if not isinstance(event, dict) or not isinstance(event.get("kind"), str) \
                    or not _KIND.fullmatch(event["kind"]):
                malformed += 1
                continue
            kinds.setdefault(event["kind"], []).append(_event_position(event, sessions))
        if kinds or malformed:
            print(f"   harness events: {sum(map(len, kinds.values())) + malformed}")
        for kind, positions in sorted(kinds.items()):
            known = [position for position in positions if position]
            print(f"     {kind}: {len(positions)}" + (f" at {'; '.join(known)}" if known else "")
                  + (f" ({len(positions) - len(known)} without a position)" if known and len(known) < len(positions)
                     else ""))
        if malformed:
            print(f"     malformed event lines: {malformed}")
        counts: dict[str, int] = {}
        for line in log.splitlines():
            text = line.split(" ", 1)[1] if re.match(r"\d\d:\d\d:\d\d ", line) else line
            words = text.split()
            if text.startswith("host error"):
                name = f"host error {_class_name(words[2]) if len(words) > 2 else 'other'}"
            elif text.startswith("stop failed"):
                name = f"stop failed {_class_name(words[2]) if len(words) > 2 else 'other'}"
            elif text.startswith("harness event"):
                name = "harness event lines"
            elif text.startswith("Traceback"):
                name = "Traceback"
            elif match := _EXCEPTION_LINE.match(text):
                name = f"exception {_class_name(match.group(1))}"
            else:
                name = None
            if name:
                counts[name] = counts.get(name, 0) + 1
            if "cap reached" in text:
                counts["cap reached"] = counts.get("cap reached", 0) + 1
        for name, count in sorted(counts.items()):
            print(f"   log: {name}: {count}")


def verdicts(path: Path, scenario_path: str, *, companion=False) -> None:
    """Check a first-review file before the split, and rename prefix keys ("L01") to full case ids.

    Refuses unless the result covers exactly the scenario's cases, each with labels A, B and C, a score of 0, 0.5 or
    1, and critical types from 1 to 5 (1 to 9 for C5). A rename happens only when every key is the prefix of one case; the
    original is kept as <name>.raw.json and nothing but the top-level keys changes."""
    ids = [case for _, _, case, _ in load(scenario_path).CASES]
    try:
        data = json.loads(path.read_text())
    except ValueError as error:
        raise SystemExit(f"invalid: not JSON ({error})")
    if not isinstance(data, dict):
        raise SystemExit("invalid: not an object")
    renamed = {}
    for key in data:
        matches = [case for case in ids if case == key or case.split("-")[0] == key]
        if len(matches) != 1:
            raise SystemExit(f"invalid: key {key!r} does not name exactly one case")
        renamed[key] = matches[0]
    if sorted(renamed.values()) != sorted(ids):
        raise SystemExit("invalid: the keys do not cover exactly the scenario's cases")
    for key, verdict in data.items():
        if not isinstance(verdict, dict) or sorted(verdict) != ["A", "B", "C"]:
            raise SystemExit(f"invalid: {renamed[key].split('-')[0]} does not have exactly labels A, B and C")
        for label, item in verdict.items():
            critical = item.get("critical") if isinstance(item, dict) else None
            if (not isinstance(item, dict) or type(item.get("score_ignoring_critical")) not in (int, float)
                    or item["score_ignoring_critical"] not in (0, 0.5, 1)
                    or not _valid_marks(critical, 9 if companion else 5)):
                raise SystemExit(f"invalid: {renamed[key].split('-')[0]}/{label} has a bad score or critical list")
    changed = [key for key, case in renamed.items() if key != case]
    if changed:
        raw = path.with_name(path.stem + ".raw.json")
        raw.write_bytes(path.read_bytes())
        path.write_text(json.dumps({renamed[key]: value for key, value in data.items()}, ensure_ascii=False, indent=1))
    print(json.dumps({"valid": True, "renamed_keys": len(changed)}))


def _checked_tally(path: Path, *, companion=False) -> dict:
    try:
        data = json.loads(path.read_text())
        totals, rows = data["totals"]["resolved"], data["rows"]
        if data.get("gate", "R4") != ("C5" if companion else "R4"):
            raise ValueError("tally belongs to a different gate")
        if (not isinstance(totals, dict) or set(totals) != set("PEF")
                or not isinstance(rows, list) or not rows):
            raise ValueError("missing totals or rows")
        calculated, cases = dict.fromkeys("PEF", 0), {}
        for row in rows:
            case, label, arm, base, marks = (row[field] for field in ("case", "label", "arm", "base", "resolved"))
            if (not isinstance(case, str) or not case or label not in ("A", "B", "C")
                    or arm not in ("P", "E", "F") or type(base) not in (int, float)
                    or base not in (0, 0.5, 1) or not _valid_marks(marks, 9 if companion else 5)):
                raise ValueError("bad row")
            labels = cases.setdefault(case, {})
            if label in labels:
                raise ValueError("duplicate case label")
            labels[label] = arm
            calculated[arm] += 0 if marks else base
        if any(set(labels) != set("ABC") or set(labels.values()) != set("PEF") for labels in cases.values()):
            raise ValueError("incomplete case")
        if any(type(value) not in (int, float) or value != calculated[arm] for arm, value in totals.items()):
            raise ValueError("totals disagree with rows")
        return data
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"invalid tally {path.name}: {error}") from error


def gate(review: Path, keys: list[str], *, companion=False, manifest: Path | None = None) -> dict:
    """The attempt-3 pass rule from the tallies and the attributions (two per gated reply; disagreement or a
    missing or invalid answer counts as memory). C5 also refuses every standing boundary or deletion error.

    With a frozen attempt manifest, the keys must be exactly its pair for this gate, and every tally must have been
    made with that manifest on that pair's scenario file (key, stem and sha256). The other pair is not read."""
    if not keys or len(set(keys)) != len(keys):
        raise SystemExit("invalid tally: expected distinct scenario keys")
    name = "C5" if companion else "R4"
    tallies = [_checked_tally(review / f"tally-{key}.json", companion=companion) for key in keys]
    bound = None
    if manifest is not None:
        frozen, frozen_hash = _manifest(manifest)
        pair = {item["key"]: item for item in manifest_scenarios(frozen, name)}
        if set(keys) != set(pair):
            raise SystemExit(f"invalid tally: gate {name} needs exactly the manifest's {name} keys "
                             f"{sorted(pair)}, not {sorted(keys)}")
        for key, data in zip(keys, tallies, strict=True):
            expected = {"key": key, "stem": PurePosixPath(pair[key]["path"]).stem, "sha256": pair[key]["sha256"]}
            if data.get("scenario") != expected:
                raise SystemExit(f"invalid tally tally-{key}.json: not the manifest's {key!r} scenario")
            if data.get("manifest") != {"attempt_id": frozen["attempt_id"], "sha256": frozen_hash}:
                raise SystemExit(f"invalid tally tally-{key}.json: not made with this manifest")
        bound = {"attempt_id": frozen["attempt_id"], "sha256": frozen_hash,
                 "scenarios": [{"key": key, **{field: pair[key][field] for field in ("path", "sha256")}}
                               for key in keys]}
    seen_cases = set()
    for data in tallies:
        cases = {row["case"] for row in data["rows"]}
        if overlap := seen_cases & cases:
            raise SystemExit(f"invalid tally: duplicate case {sorted(overlap)[0].split('-')[0]} across scenarios")
        seen_cases.update(cases)
    totals, critical, causes, protected = {}, {}, {}, {}
    for key, data in zip(keys, tallies, strict=True):
        for arm, value in data["totals"]["resolved"].items():
            totals[arm] = totals.get(arm, 0) + value
        for row in data["rows"]:
            if row["resolved"]:
                critical.setdefault(row["arm"], []).append(f"{row['case']}/{row['label']}")
                if companion and set(row["resolved"]) & {7, 8}:
                    protected.setdefault(row["arm"], []).append(f"{row['case']}/{row['label']}")
                if row["arm"] in "PE":
                    answers = []
                    for attempt in ("1", "2"):
                        path = review / f"attribution-{key}" / f"{row['case'].split('-')[0]}-{row['label']}.{attempt}.json"
                        try:
                            answer = json.loads(path.read_text())
                            answers.append(answer.get("cause") if isinstance(answer, dict) else None)
                        except (OSError, ValueError):
                            answers.append(None)
                    cause = "host" if answers == ["host", "host"] else "memory"
                    causes[f"{row['case']}/{row['label']}"] = {"answers": answers, "cause": cause}
    reference = totals.get("F", 0)
    verdict = {}
    for arm in "PE":
        replies = critical.get(arm, [])
        memory = [reply for reply in replies if causes[reply]["cause"] == "memory"]
        host = [reply for reply in replies if causes[reply]["cause"] == "host"]
        verdict[arm] = {"total": totals.get(arm, 0), "reference": reference,
                        "not_worse": totals.get(arm, 0) >= reference - 1, "memory_caused": memory,
                        "host_caused": host, "reference_critical": len(critical.get("F", [])),
                        "passes": totals.get(arm, 0) >= reference - 1 and not memory
                        and len(host) <= len(critical.get("F", [])) and not protected.get(arm)}
        if companion:
            verdict[arm]["boundary_or_deletion_errors"] = protected.get(arm, [])
    result = {"arms": verdict, "attributions": causes, name: all(item["passes"] for item in verdict.values())}
    if companion:
        result["strict_boundaries_and_deletions"] = True
    if bound:
        result["manifest"] = bound
    (review / ("gate-c5.json" if companion else "gate.json")).write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return result


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    companion = "--companion" in args
    if companion:
        if command not in ("verdicts", "tally", "gate") or args.count("--companion") != 1:
            raise SystemExit("--companion is valid once for verdicts, tally or gate")
        args.remove("--companion")
    manifest = None
    if "--manifest" in args:
        at = args.index("--manifest")
        if command not in ("tally", "gate") or args.count("--manifest") != 1 or at + 1 >= len(args):
            raise SystemExit("--manifest PATH is valid once for tally or gate")
        manifest = Path(args[at + 1])
        del args[at:at + 2]
    if command == "split":
        split(Path(args[0]), Path(args[1]), Path(args[2]), args[3], Path(args[4]))
    elif command == "tally":
        tally(Path(args[0]), Path(args[1]), args[2], args[3], companion=companion, manifest=manifest)
    elif command == "attribution-inputs":
        attribution_inputs(Path(args[0]), Path(args[1]), args[2], args[3], Path(args[4]))
    elif command == "validity":
        if not validity([Path(arg) for arg in args])["valid"]:
            raise SystemExit(1)
    elif command == "r5-inputs":
        r5_inputs(Path(args[0]), Path(args[1]), args[2], args[3], Path(args[4]))
    elif command == "r5-check":
        r5_check(Path(args[0]), Path(args[1]), Path(args[2]))
    elif command == "actions-digest":
        actions_digest(Path(args[0]), Path(args[1]), args[2], args[3], [Path(arg) for arg in args[4:]])
    elif command == "verdicts":
        verdicts(Path(args[0]), args[1], companion=companion)
    elif command == "diagnose":
        diagnose([Path(arg) for arg in args])
    elif command == "gate":
        result = gate(Path(args[0]), args[1:], companion=companion, manifest=manifest)
        if not result["C5" if companion else "R4"]:
            raise SystemExit(1)  # After the gate file is written: a failed gate is reported, then exits nonzero.
    else:
        raise SystemExit(__doc__)
