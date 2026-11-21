"""Run the speaker-attribution test on one or more adapters and print the result table. No model is called.

    uv sync --extra embedded --extra semantic
    uv run python evaluations/speaker-attribution/run.py --out RUN_DIR

``RUN_DIR`` is a scratch directory this run owns: the disposable memBrain profiles, their databases, the embedded
database binaries and the embedding model cache all go there, and the stopped databases are removed after use
(``--keep`` leaves them). Rows and the table are written to ``--results`` (default ``RUN_DIR/results``).

Modes:

- ``isolated``: each case gets its own empty memory holding only that case's conversation.
- ``shared``: one memory holds every case and the filler sessions in date order, as one person's history; every
  question is then asked of it, each in a new conversation.

Budget: memBrain decides the size of its own context (cut at ``--cap``). Every other arm gets, question by
question, exactly the number of characters memBrain used for that question in the same mode, as in the
LongMemEval comparison. Without a memBrain arm in the run, ``--budget`` is used for every question.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import kit  # noqa: E402

FREE_BYTES = 2 * 1024 ** 3
MAX_WINDOWS_ROOT = 60
SESSION_NAME = re.compile(r"speaker-attribution-question-\d+")
ARMS = ("membrain", "plain", "plain-unlabelled")


def log(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def isolate_environment(out: Path) -> list[str]:
    """Keep this process and the services it starts away from the user's own memBrain and host memory files.

    memBrain variables are removed (a ``MEMBRAIN_DIRECTORY`` could point at a real profile, an extraction key at a
    paid model), and the per-user locations the runtime may read are pointed at empty directories inside ``out``.
    Returns the names of the variables removed; their values are never printed or stored.
    """
    removed = sorted(name for name in os.environ if name.startswith(("MEMBRAIN_", "AGENT_MEMORY_")))
    for name in removed:
        del os.environ[name]
    home = out / "h"  # Short: Windows paths over 260 characters break the database archive's extraction.
    for name, sub in (("LOCALAPPDATA", "la"), ("XDG_CACHE_HOME", "cache"), ("CLAUDE_CONFIG_DIR", "claude"),
                      ("HERMES_HOME", "hermes"), ("OPENCLAW_WORKSPACE", "openclaw"), ("CODEX_HOME", "codex")):
        path = home / sub
        path.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(path)
    return removed


def make(arm: str, model_cache: Path, no_embeddings: bool):
    if arm == "membrain":
        from adapter_membrain import MemBrain

        return MemBrain(model_cache)
    if arm in ("plain", "plain-unlabelled"):
        from adapter_plain import PlainRetrieval

        return PlainRetrieval(None if no_embeddings else model_cache, roles=arm == "plain")
    raise SystemExit(f"Unknown arm {arm!r}. Third-party systems are added by writing an adapter: see README.md.")


def remove(path: Path) -> str | None:
    """Delete a directory this run created; returns an error message if Windows still holds a file open."""
    for attempt in range(10):
        try:
            shutil.rmtree(path)
            return None
        except FileNotFoundError:
            return None
        except OSError as error:
            if attempt == 9:
                return f"{type(error).__name__}: {error}"
            time.sleep(3)
    return None


def ask(adapter, question: kit.Question, budget: int, turns: list[kit.Turn], mode: str) -> list[dict]:
    began = time.perf_counter()
    text = adapter.context(question.text, budget=budget)
    seconds = time.perf_counter() - began
    contexts = {adapter.name: text}
    if hasattr(adapter, "variants"):
        contexts.update(adapter.variants())
    rows = []
    for arm, context in contexts.items():
        cut = context[:budget]
        lines, unverifiable = kit.verified_lines(adapter, cut)
        row = {"mode": mode, "arm": arm, "case": question.case, "question": question.id, "kind": question.kind,
               "asks": question.asks, "text": question.text, "budget": budget, "characters": len(cut),
               "over_budget": len(context) > budget, "seconds": round(seconds, 3),
               "unverifiable_lines": unverifiable, **kit.score(question, lines, turns), "context": cut}
        if hasattr(adapter, "details"):
            row.update(adapter.details(cut))
        rows.append(row)
    return rows


def run_arm(arm: str, mode: str, cases, filler, args, budgets: dict) -> list[dict]:
    adapter = make(arm, args.model_cache, args.no_embeddings)
    turns = kit.all_turns(cases, filler)
    rows, problems = [], []
    groups = ([(case.id, list(case.sessions), list(case.questions)) for case in cases] if mode == "isolated" else
              [("shared", kit.shared_sessions(cases, filler), [q for case in cases for q in case.questions])])
    for name, sessions, questions in groups:
        workdir = args.out / "work" / mode / arm / name
        workdir.mkdir(parents=True, exist_ok=True)
        began = time.monotonic()
        try:
            adapter.reset(workdir)
            for session in sessions:
                adapter.ingest(session)
            adapter.ready()
            def budget_for(question):
                return budgets.get((mode, question.key), args.budget) if arm != "membrain" else args.cap

            for question in questions:
                rows.extend(ask(adapter, question, budget_for(question), turns, mode))
            if mode == "shared" and questions:
                # Asking does not change later answers: the first question again, after all the others.
                again = adapter.context(questions[0].text, budget=budget_for(questions[0]))
                first = next(row for row in rows if row["arm"] == adapter.name and row["case"] == questions[0].case
                             and row["question"] == questions[0].id)
                again = again[:first["budget"]]
                # memBrain's notice names the conversation it was written for; that name differs by design.
                stable = SESSION_NAME.sub("#", again) == SESSION_NAME.sub("#", first["context"])
                rows.append({"mode": mode, "arm": adapter.name, "check": "repeat_first_question", "stable": stable,
                             "identical": again == first["context"], "context": again})
                if not stable:
                    log(arm, mode, "WARNING: asking the first question again gave a different context")
        finally:
            try:
                adapter.close()
            except Exception as error:  # Never hide the error that stopped the run.
                log(arm, mode, name, "close failed:", type(error).__name__, error)
        timing = {"mode": mode, "arm": adapter.name, "group": name, "seconds": round(time.monotonic() - began, 1),
                  **getattr(adapter, "timings", {})}
        rows.append({"check": "timing", **timing})
        if not args.keep:
            error = remove(workdir)
            if error:
                problems.append(f"{workdir}: {error}")
        log(arm, mode, name, "done in", timing["seconds"], "s")
    for problem in problems:
        log("could not remove", problem)
    return rows


def write(rows: list[dict], results: Path, mode: str, arm: str) -> None:
    results.mkdir(parents=True, exist_ok=True)
    with (results / f"rows-{mode}-{arm}.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def read(results: Path) -> list[dict]:
    rows = []
    for path in sorted(results.glob("rows-*.jsonl")):
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return rows


def report(results: Path) -> str:
    rows = read(results)
    scored = [row for row in rows if "passed" in row]
    order = {arm: position for position, arm in enumerate(("membrain", "membrain+recall-tool", *ARMS[1:]))}
    scored.sort(key=lambda row: (("isolated", "shared").index(row["mode"]), order.get(row["arm"], 99)))
    table = kit.Summary(scored).table()
    lines = ["# Speaker-attribution results", "", table, ""]
    checks = [row for row in rows if row.get("check") == "repeat_first_question"]
    for row in checks:
        same = "the same" if row["stable"] else "a DIFFERENT"
        if row["stable"] and row.get("identical") is False:
            same += " (apart from the conversation name in memBrain's notice)"
        lines.append(f"- {row['mode']}, {row['arm']}: asking the first question again gave {same} context.")
    lines += ["", "## Questions that did not pass", ""]
    for row in scored:
        if row["passed"]:
            continue
        reasons = []
        for name, label in (("missing_user_statement", "user statement not found as the user's"),
                            ("missing_adopted", "adopted content not found"),
                            ("missing_assistant_statement", "suggestion not found as the assistant's")):
            if row[name]:
                reasons.append(f"{label}: {', '.join(row[name])}")
        for finding in row["findings"]:
            if finding["kind"] != "attributed_to_assistant":
                reasons.append(f"{finding['kind']} {finding['phrase']!r} in: {finding['line'][:160]}")
        lines.append(f"- **{row['mode']}, {row['arm']}, {row['case']}/{row['question']}** ({row['kind']}, "
                     f"{row['asks']}): " + "; ".join(reasons))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, required=True, help="Scratch directory owned by this run")
    parser.add_argument("--results", type=Path, help="Where rows and the table go (default OUT/results)")
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--modes", default="isolated,shared")
    parser.add_argument("--model-cache", type=Path, help="Directory holding the pinned embedding model "
                        "(default OUT/model-cache; downloaded there and checksum-verified if missing)")
    parser.add_argument("--budget", type=int, default=9000, help="Characters per question when no memBrain arm "
                        "runs in the same mode")
    parser.add_argument("--cap", type=int, default=20000, help="Upper limit on memBrain's own context")
    parser.add_argument("--no-embeddings", action="store_true", help="Plain retrieval by BM25 only")
    parser.add_argument("--keep", action="store_true", help="Keep the stopped databases after the run")
    parser.add_argument("--only", default="", help="Comma-separated case ids, for a quick smoke run")
    parser.add_argument("--report", action="store_true", help="Only print the table from existing rows")
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.results = (args.results or args.out / "results").resolve()
    if args.report:
        print(report(args.results))
        return
    if os.name == "nt" and len(str(args.out)) > MAX_WINDOWS_ROOT:
        raise SystemExit(f"Use a shorter --out on Windows (at most {MAX_WINDOWS_ROOT} characters): the embedded "
                         "database's files would pass the 260-character path limit under it.")
    args.out.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(args.out).free
    if free < FREE_BYTES:
        raise SystemExit(f"Only {free / 1024 ** 3:.1f} GiB free under {args.out}; at least 2 GiB are required.")
    args.model_cache = (args.model_cache or args.out / "model-cache").resolve()
    removed = isolate_environment(args.out)
    if removed:
        log("removed from this process's environment:", ", ".join(removed))
    cases, filler = kit.load()
    if args.only:
        cases = [case for case in cases if case.id in args.only.split(",")]
    log(len(cases), "cases,", sum(len(case.questions) for case in cases), "questions,", len(filler), "filler sessions")
    arms = [arm.strip() for arm in args.arms.split(",") if arm.strip()]
    arms.sort(key=lambda arm: arm != "membrain")  # memBrain first: the other arms take its sizes.
    for mode in [mode.strip() for mode in args.modes.split(",") if mode.strip()]:
        budgets: dict = {}
        for arm in arms:
            log("arm", arm, "mode", mode)
            rows = run_arm(arm, mode, cases, filler, args, budgets)
            if arm == "membrain":
                budgets = {(mode, f"{row['case']}/{row['question']}"): row["characters"] for row in rows
                           if row.get("arm") == "membrain" and "passed" in row}
            write(rows, args.results, mode, arm)
    text = report(args.results)
    (args.results / "table.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
