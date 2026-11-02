# Final behavioral acceptance plan (R4), attempt 4, frozen before any paid call

[Attempt 3](v1-2026-11-04-final-acceptance-3.md) was invalid: in scenario K, two arms each recorded one empty host reply. Its scenario J was scored, and found two memBrain defects. Both are fixed:
- the message that ends a pause was lost;
- an older note took a newer one's place.

This attempt runs the repaired runtime on two new held-out scenarios, L and M. Wherever this plan does not say otherwise, [attempt 3's plan](v1-2026-11-04-final-acceptance-plan-3.md) applies. The pass rule, the review instructions and the attribution rules are all unchanged.

An independent reviewer approved the first draft of this plan with five required plan fixes and six required fixes to scenario L, and this version makes all of them. Scenario M was added afterwards and goes through the same review before the freeze.

## Candidate

- **Runtime.** Commit `a5586122888309a82872893caf6e7a0afe97e6fe`. Every launcher pins it as of commit `a222b02`.
- **Install check.** The release install check passed 17 of 17 on this runtime, upgrading from attempt 3's runtime `9a1816a` ([results](release-install-2026-11-05.json)).
- **Freeze.** The runtime is frozen until scoring ends.
- **Before the first paid call**, the outputs of these checks are saved:
  - the pin check reports 2 passed;
  - `git status --porcelain` is empty;
  - `git diff a558612 -- plugins/membrain/skills src/membrain` is empty;
  - `MEMBRAIN_SRC` is unset, and `membrain.__file__` resolves into this checkout.

**Every change since attempt 3's runtime `9a1816a`** (`git diff 9a1816a a558612 -- src plugins integrations`), each with tests:
- **Resumed turns are stored.** When the agent resumes recording because the user's current message asks for it (`memory_resume`, `membrain_resume`), that message and the reply are stored. Claude Code reads the message from the transcript, skipping meta and summary entries; OpenClaw sends it with the stop hook. A resume from the memory page or the command line still stores nothing from a turn in progress, and neither does a turn that is paused again during the message.
- **Newer notes keep their place.** When notes do not all fit, older notes of a rank are not shown in place of a newer one of the same rank that does not fit.
- **What the host is told** (arm `P`):
  - the skill now says the message that asks to resume is stored with the reply, so the host should save any update it brings as a note as usual;
  - the `memory_resume` description now says the current message and the reply are recorded;
  - the resume tools of Hermes, AstrBot and OpenClaw say the same.
- **Launchers** are re-pinned to `a5586122888309a82872893caf6e7a0afe97e6fe`.

## Inputs

| File | SHA-256 |
| --- | --- |
| [Scenario L](v1-2026-11-05-acceptance-scenario-l.py), mainly English with one session in German | `94f40fcc3ab42e89e36339d55ea9ced35b4fd25597ff5551448d29da44c39c6c` |
| [Scenario M](v1-2026-11-05-acceptance-scenario-m.py), mainly Chinese with one session in English | `12ab30995fe9fe3cf518107de81b38d4ffea22b2423ef87ef2a7beef0d6814b2` |
| [Harness](v1-2026-10-29-phase-b-harness.py) | `65a2dc5e7ba2e79caff4a11ce2775c287a2f41e1e7fe35fd4662fc1ada58f5a3` |
| [Blinding](v1-2026-10-29-phase-b-blind.py) | `320b8c2d55e7551c90ee229079b352da8d24e360fa42f6b2cb1c54dbfcc887d6` |
| [Date pre-check](v1-2026-11-02-date-precheck.py) | `3e04a9915df6b52351806ebf4bb9ec8c368875762d94140071f4284b832065a6` |
| [Review pipeline](acceptance_review.py) | `b257a55a7ee7180c7221122f44133e88f322539798d1a5364536941985d9eefa` |
| [First-reviewer instructions](acceptance-review/first.md) | `4bc86a35139ba297d62a46fa90b2600440a04a6f30a2d02480344e4f337475a6` |
| [Re-check instructions](acceptance-review/recheck.md) | `7f1efbbe87e8087962bdd2a3c2ebdd237900c7b7155188450c512dc1b734c4da` |
| [Resolution instructions](acceptance-review/resolve.md) | `838920c18b2fe0b1356c1e53d7061324ac4a82d2a9540bf565b471ab02fa8c86` |
| [Attribution instructions](acceptance-review/attribute.md) | `737865ae9e982b19c242d26e6a1865e8f136cc686eb72f9e2230652ffc97648f` |

**Harness changes since attempt 3:**
- **Empty replies.** An empty host reply (no answer and no tool call) counts as a malformed response and is retried inside the call, like other malformed responses: up to four tries in all, with a growing wait. Every try counts toward the call cap.
- **Resumed turns.** A turn in which the agent resumed recording is stored from the user's own message, as the plugin's Stop hook now does. The harness requires `turn_resumed` from the runtime, so the behaviour cannot be silently missing.

## Scenarios

- **Why K was dropped.** Attempt 3's report named K's two empty turns by session id and gave a completion-token count. While diagnosing those turns, the developer printed both rows' usage, seconds, reply and tool calls, and the first 800 characters of each transcript. That showed K's full first user message in one session and the start of a memory block in the other. K is therefore no longer unseen, and it is not used.
- **K's attempt-3 results** are never scored, opened or used for any decision, whatever this attempt's outcome.
- **Who wrote L and M.** A fresh agent wrote each one under the same brief and restrictions as J and K. Neither agent was allowed to open any earlier acceptance scenario (F onwards), any result, or anything about the product.
- **What the developer has seen of L and M:** only their hashes and the date pre-check's last line.
- **Scenario fixes.** The reviewer's scenario findings go to a file the developer does not open. An agent other than the developer applies the required fixes from that file. Afterwards the new hashes are recorded here, and the date pre-check is re-run on L and M. Its full output goes to the evidence, and the developer sees only its last line.

## Validity before scoring

- **When validity runs.** `acceptance_review.py validity` runs on all six run directories after the last arm finishes, before any blinding, review or diagnosis.
- **Exhausted retries.** If a call's retries run out, the arm stops with a Traceback. There is no mid-run resume. The guard then finds the Traceback, and the attempt is invalid.
- **If the attempt is invalid:**
  - neither scenario is scored, even one whose own three arms are valid;
  - both stay held out and run again in new, empty directories;
  - the diagnosis reads only the validity output and the harness log's error lines (arm, session id, turn and error), never a row's input, reply, memory context or transcript.
- **Repeated failures.** If the same scenario is invalid twice in a row, the third run is replaced by a written diagnosis that follows the same reading rule. The attempt then stops without a pass or fail, for a decision by the owner.
- **The report** gives each arm's count of retried empty replies (`host error ValueError empty reply` lines), as well as any failure.

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

## Stop rules, spending, evidence

These are as in attempt 3, with the validity rules above.
- **Report:** `evaluations/v1-2026-11-05-final-acceptance-4.md`.
- **Spending:** there is no fixed cap (owner approval of 2026-11-02). The balance is read before the attempt (308.87 CNY after attempt 3) and after each scenario.
