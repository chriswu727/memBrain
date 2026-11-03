# Final behavioral acceptance plan (R4), attempt 4, frozen before any paid call

[Attempt 3](v1-2026-11-04-final-acceptance-3.md) was invalid: in scenario K, two arms each recorded one empty host reply. Its scenario J was scored, and found two memBrain defects. Both are fixed:
- the message that ends a pause was lost;
- an older note took a newer one's place.

This attempt runs the repaired runtime on two new held-out scenarios, L and M. Wherever this plan does not say otherwise, [attempt 3's plan](v1-2026-11-04-final-acceptance-plan-3.md) applies. The pass rule, the review instructions and the attribution rules are all unchanged.

**Review history.**
- A first independent reviewer approved a draft with five required plan fixes and six required fixes to scenario L.
- Scenario M then replaced K.
- A second independent reviewer approved the revised plan with five more required plan fixes and seven required fixes to M, and found that L's fixes had all been applied.
- This version makes every required fix.

## Candidate

- **Runtime.** Commit `a5586122888309a82872893caf6e7a0afe97e6fe`. Commit `a222b02` re-pins every launcher to it; that commit changes only the nine launcher files.
- **Install check.** The release install check passed 17 of 17 on this runtime, upgrading from attempt 3's runtime `9a1816a` ([results](release-install-2026-11-05.json)).
- **Freeze.** The runtime, the harness, the pipeline, the run script and the scenarios are frozen at the hashes below from the first paid call until scoring ends. A re-run after an invalid attempt uses the same frozen files.
- **Before the first paid call**, the outputs of these checks are saved:
  - the pin check reports 2 passed;
  - `git status --porcelain` is empty;
  - `git diff a558612 -- plugins/membrain/skills src/membrain` is empty;
  - `MEMBRAIN_SRC` is unset, and `membrain.__file__` resolves into this checkout.

**Every runtime change since attempt 3's runtime `9a1816a`** (`git diff 9a1816a a558612 -- src plugins integrations`):
- **Resumed turns are stored.**
  - When the agent resumes recording because the user's current message asks for it (`memory_resume`, `membrain_resume`), that message and the reply are stored.
  - Claude Code's Stop hook reads the message from the transcript.
  - OpenClaw sends it with the stop hook.
  - `ChatMemory.resume` now defaults to `current_turn=True`, so every caller of it stores the current message, not only AstrBot's tool.
  - A resume from the memory page or the command line still stores nothing from a turn in progress, and neither does a turn that is paused again during the message.
  - Python tests cover the host, the MCP tools and the Stop hook. OpenClaw's own tests are unchanged and still pass.
- **The Stop hook skips Claude Code's own entries.** It now passes over `isMeta` and `isCompactSummary` entries when it reads the transcript, both for the user's prompt and for the reply (`last_assistant_message`).
- **Newer notes keep their place.** When notes do not all fit, older notes of a rank are not shown in place of a newer one of the same rank that does not fit.
- **What the host is told** (arm `P`):
  - the skill now says the message that asks to resume is stored with the reply, so the host should save any update it brings as a note as usual;
  - the `memory_resume` description now says the current message and the reply are recorded;
  - the resume tools of Hermes, AstrBot and OpenClaw say the same.
- **Launchers.** In this diff the launchers pin `a7cbda6`. The pin to `a558612` comes from commit `a222b02`, which is not part of the diff.

## Inputs

| File | SHA-256 |
| --- | --- |
| [Scenario L](v1-2026-11-05-acceptance-scenario-l.py), mainly English with one session in German | `94f40fcc3ab42e89e36339d55ea9ced35b4fd25597ff5551448d29da44c39c6c` |
| [Scenario M](v1-2026-11-05-acceptance-scenario-m.py), mainly Chinese with one session in English | `767170cb78fe873c53a195a9248b26427db8c1e2f5b09110c6813f171b472de0` |
| [Harness](v1-2026-10-29-phase-b-harness.py) | `65a2dc5e7ba2e79caff4a11ce2775c287a2f41e1e7fe35fd4662fc1ada58f5a3` |
| [Run script](v1-2026-11-05-run-scenario.sh) | `a983d5a5683c09003f0247649938c0987391bb6b23cfb194aaa8460623a9a583` |
| [Blinding](v1-2026-10-29-phase-b-blind.py) | `320b8c2d55e7551c90ee229079b352da8d24e360fa42f6b2cb1c54dbfcc887d6` |
| [Date pre-check](v1-2026-11-02-date-precheck.py) | `3e04a9915df6b52351806ebf4bb9ec8c368875762d94140071f4284b832065a6` |
| [Review pipeline](acceptance_review.py) | `c0cb4ae9d4f6e0c713d2d138f56edcf0e1bd9efe7f5a682194426d9bf632f1ac` |
| [First-reviewer instructions](acceptance-review/first.md) | `4bc86a35139ba297d62a46fa90b2600440a04a6f30a2d02480344e4f337475a6` |
| [Re-check instructions](acceptance-review/recheck.md) | `7f1efbbe87e8087962bdd2a3c2ebdd237900c7b7155188450c512dc1b734c4da` |
| [Resolution instructions](acceptance-review/resolve.md) | `838920c18b2fe0b1356c1e53d7061324ac4a82d2a9540bf565b471ab02fa8c86` |
| [Attribution instructions](acceptance-review/attribute.md) | `737865ae9e982b19c242d26e6a1865e8f136cc686eb72f9e2230652ffc97648f` |

**Harness changes since attempt 3:**
- **Empty replies.** An empty host reply (no answer and no tool call) counts as a malformed response and is retried inside the call: up to four tries in all, with a growing wait. Every try counts toward the call cap.
- **Resumed turns.** A turn in which the agent resumed recording is stored from the user's own message, as the plugin's Stop hook now does. The harness calls the runtime's `turn_resumed` directly, so the behaviour cannot be silently missing.

**Pipeline changes since attempt 3:**
- **`validity`** now also refuses a run whose `run.log` is missing, empty or does not end with the harness's `<arm> <scenario> finished` line.
- It names a failing turn by its position in the scenario, not by session id.
- It reports each arm's count of retried empty replies.
- **A new `diagnose` command** prints, for each arm, only:
  - how many turns are done, and the position of the last one;
  - the positions of any empty replies;
  - the log's error lines: `host error`, `cap reached`, `harness event`, `Traceback` with its frame lines, and the exception line, each cut to 200 characters.

  It never prints the per-turn progress lines, because they show memory tool arguments. Nor does it print any row's input, reply, memory context or transcript.
- `split`, `tally`, `attribution-inputs` and `gate` are unchanged.

## Scenarios

- **Why K was dropped.** Attempt 3's report named K's two empty turns by session id and gave a completion-token count. While diagnosing those turns, the developer printed both rows' usage, seconds, reply and tool calls, and the first 800 characters of each transcript. That showed K's full first user message in one session and the start of a memory block in the other. K is therefore no longer unseen, and it is not used.
- **K's attempt-3 results** are never scored, opened or used for any decision, whatever this attempt's outcome.
- **Who wrote L and M.** A fresh agent wrote each one under the same brief and restrictions as J and K. Neither agent was allowed to open any earlier acceptance scenario (F onwards), any result, or anything about the product.
- **Who fixed them.** Agents other than the developer applied the reviewers' required fixes from findings files the developer does not open.
- **What the developer has seen of L and M:** only their hashes, the case ids named in the reviews, the reviewers' counts of fixes, and the date pre-check's last line.
- **Date pre-check.** It was re-run on the final L and M and reports `failures: 0` for all 64 sessions. Its full output is in the evidence.

## Running

Each scenario's three arms run in parallel with:

```
DEEPSEEK_API_KEY=… MEMBRAIN_MODEL_CACHE=… evaluations/v1-2026-11-05-run-scenario.sh SCENARIO.py OUT_ROOT KEY
```

- **Logging.** Arm `X` runs in `OUT_ROOT/KEY-X`, with stdout and stderr appended to `OUT_ROOT/KEY-X/run.log`.
- **No reused directories.** The script refuses a run directory that already exists. The harness is never started a second time on a run directory, since it would resume from the turns already in the results file. Doing so by any other means makes the attempt invalid.
- **Order.** L runs first, then M, and the balance is read after each.

**Two inherited stop rules are replaced:**
- "Errors that resume … resume from the last completed turn" (attempts 1 to 3). Transient errors and empty replies are retried inside the call. If a call's retries run out, the arm stops with a Traceback, and the attempt is invalid.
- "Degraded runs … never void a run" (attempts 1 and 2). Harness events are still reported, but any finding of the validity check below makes the attempt invalid, including an index wait that timed out.

## Validity before scoring

- **When validity runs.** After the last arm of the last scenario finishes, `acceptance_review.py validity` runs on all six run directories, before any blinding, review or diagnosis.
- **What it refuses:**
  - a missing, empty or unfinished `run.log`;
  - a missing turn or an empty reply;
  - a reached call cap;
  - a Traceback;
  - an index wait that timed out.
- **If the attempt is invalid:**
  - neither scenario is scored, even one whose own three arms are valid;
  - the only diagnosis is `acceptance_review.py diagnose` on the six directories, and nothing else in them is opened;
  - both scenarios stay held out, and run again in new, empty directories under the same frozen files and hashes;
  - any change to the runtime, harness, pipeline, run script or scenarios before a re-run needs a revised plan and a new independent review.
- **Repeated failures.** If the re-run is invalid as well, the attempt stops without a pass or fail. A written diagnosis, from `diagnose` only, goes to the owner for a decision.
- **The report** gives each arm's count of retried empty replies, from `validity`.

## Arms, scoring, attribution

These are unchanged from attempt 3.
- **Arms:** `P`, `E` and `F`.
- **Review:** first review, split, per-case re-check, resolution under R1 to R3, then the tally.
- **Attribution:** two fresh agents per gated critical reply. The cause is `host` only when both answer `host`.

## Pass rule

This is the same as attempt 3. Each gated arm passes when all three of these hold:
1. its total over L and M is at least the reference arm's total minus 1;
2. none of its standing critical errors is memory-caused;
3. its number of host-caused standing critical errors is at most the reference arm's number of standing critical errors.

`acceptance_review.py gate` computes this. R4 passes when both gated arms pass.

The report also gives:
- the literal totals;
- the absolute totals against the lowest reference total so far (16.5);
- what attempts 1 and 2's rule would have decided.

## Limitations

- **The real transcript path is not exercised.** The harness emulates the Stop hook with the user's clean message. A test covers reading a resumed prompt from a Claude Code transcript, including skipping meta entries, but no real Claude Code session runs in this attempt.

## Spending, report, evidence

- **Spending:** there is no fixed cap (owner approval of 2026-11-02). The balance is read before the attempt (308.87 CNY after attempt 3) and after each scenario.
- **Report:** `evaluations/v1-2026-11-05-final-acceptance-4.md`.
- **Evidence archive:** as in attempt 3, plus the date pre-check output and the validity output.
