# Final behavioral acceptance plan (R4), attempt 5, frozen before any paid call

[Attempt 4](v1-2026-11-05-final-acceptance-4.md) was valid. Its proxy arm `E` passed every criterion. The plugin arm `P` failed on a single reply, M06-C.

In M06-C, recall served the assistant's own earlier suggested itinerary, and the host presented it as the user's original plan. Attempt 3's J07-C had shown the same pattern. The owner chose to repair this and run a new attempt (2026-11-05).

Wherever this plan does not say otherwise, [attempt 4's plan](v1-2026-11-05-final-acceptance-plan-4.md) applies in full. That covers the arms, running, the validity check before scoring, the reading rule for an invalid run, review, attribution, the pass rule and the report contents. Nothing in the review instructions, the attribution rules, the pass rule or the harness has changed. The run script changed in Revision 2 (at the end of this plan). The pipeline gains one command (`verdicts`, below).

An independent reviewer approved a draft of this plan with five required plan fixes and seven required scenario fixes, and this version makes all of them.

## Candidate

- **Runtime.** Commit `b6d725ad8a981c30873cfa4a93e5596284b9470c`. Commit `d541ea1` re-pins every launcher to it; that commit changes only the nine launcher files.
- **Install check.** The release install check passed 17 of 17 on this runtime, upgrading from attempt 3's runtime `9a1816a` ([results](release-install-2026-11-06.json)). The upgrade from attempt 4's runtime `a558612` was not run separately; the two runtimes differ only in recall header text and the skill.
- **Freeze.** The runtime, the harness, the pipeline, the run script and the scenarios are frozen at the hashes below from the first paid call until scoring ends. A re-run after an invalid attempt uses the same frozen files, except as Revision 2 records for the run script.
- **Before the first paid call**, the outputs of these checks are saved:
  - the pin check reports 2 passed;
  - `git status --porcelain` is empty;
  - `git diff b6d725a -- plugins/membrain/skills src/membrain` is empty;
  - `MEMBRAIN_SRC` is unset, and `membrain.__file__` resolves into this checkout.

**Every runtime change since attempt 4's runtime `a558612`** (`git diff a558612 b6d725a -- src plugins integrations`):
- **Both recall headers** (statement recall and message recall, `membrain.host.ASSISTANT_LINES`) now end with one more sentence: lines marked "assistant said" are the host's own earlier replies, and a suggestion, draft or plan there is not the user's decision or a fact about the user unless a "user said" line confirms it.
- **The skill's "Searching on purpose" section** says the same in one line. This changes what the host is told in arm `P`. Arm `E` gets the recall header change through the proxy.
- **Launchers.** In this diff the launchers pin `a558612`. The pin to `b6d725a` comes from commit `d541ea1`, which is not part of the diff.
- **Tests:** `tests/test_plugin.py` checks the sentence in both recall formats.

## Inputs

| File | SHA-256 |
| --- | --- |
| [Scenario N](v1-2026-11-06-acceptance-scenario-n.py), mainly English with one session in German | `5dd23f7638df698edc4ef6c8b0dbb1836a2d311c7968fbee3a157de9925fd732` |
| [Scenario O](v1-2026-11-06-acceptance-scenario-o.py), mainly Chinese with one session in English | `dbbab96f821fb74394af615b9d391636695978b6785252e2408c50f04471dc39` |
| [Harness](v1-2026-10-29-phase-b-harness.py) (unchanged since attempt 4) | `65a2dc5e7ba2e79caff4a11ce2775c287a2f41e1e7fe35fd4662fc1ada58f5a3` |
| [Run script](v1-2026-11-05-run-scenario.sh) (Revision 2; runs 1 and 2 used `a983d5a5683c09003f0247649938c0987391bb6b23cfb194aaa8460623a9a583`) | `82e4cf00766de874fe9154aa3d16fa6d794b59f1439bf8ee123930dc2a16cdf6` |
| [Blinding](v1-2026-10-29-phase-b-blind.py) | `320b8c2d55e7551c90ee229079b352da8d24e360fa42f6b2cb1c54dbfcc887d6` |
| [Date pre-check](v1-2026-11-02-date-precheck.py) | `3e04a9915df6b52351806ebf4bb9ec8c368875762d94140071f4284b832065a6` |
| [Review pipeline](acceptance_review.py) (adds `verdicts`) | `6d622d748344f7e692af7a776bc2d6c98760276fd0cd9a9bf77d55dc4a62f5b7` |
| [First-reviewer instructions](acceptance-review/first.md) | `4bc86a35139ba297d62a46fa90b2600440a04a6f30a2d02480344e4f337475a6` |
| [Re-check instructions](acceptance-review/recheck.md) | `7f1efbbe87e8087962bdd2a3c2ebdd237900c7b7155188450c512dc1b734c4da` |
| [Resolution instructions](acceptance-review/resolve.md) | `838920c18b2fe0b1356c1e53d7061324ac4a82d2a9540bf565b471ab02fa8c86` |
| [Attribution instructions](acceptance-review/attribute.md) | `737865ae9e982b19c242d26e6a1865e8f136cc686eb72f9e2230652ffc97648f` |

## Scenarios

- **Who wrote N and O.** A fresh agent wrote each one under the same brief and restrictions as L and M. Neither agent was allowed to open any earlier acceptance scenario (F onwards), any result, or anything about the product.
- **L and M have been scored and read**, so they are not used again.
- **What the developer has seen of N and O:** only their hashes, the date pre-check's last line, and the case prefixes and fix counts the reviews report.
- **Scenario fixes** are handled as in attempt 4. An independent reviewer writes the scenario findings to a file the developer does not open, and an agent other than the developer applies the required fixes. The final hashes are recorded here, and the date pre-check is re-run on N and O. Its full output goes to the evidence, and the developer sees only its last line.

## Running and keys

- **Order.** N runs first, then O, each with the run script as revised in Revision 2.
- **Run keys:** `n` and `o`. The run directories are `OUT_ROOT/n-P`, `n-E`, `n-F`, `o-P`, `o-E` and `o-F`. Every review file is named by its key: `sheet-<key>.md`, `verdicts-<key>.json`, `recheck-<key>/`, `resolution-<key>.json`, `tally-<key>.json` and `attribution-<key>/`.
- **The balance** is read after each scenario.

## Checking review outputs

In attempt 4 both first reviewers keyed their verdicts by case prefix instead of the full case id, and the keys were renamed by hand. That is now done by a command whose output is archived.

**First review.**
- `acceptance_review.py verdicts verdicts-<key>.json SCENARIO` runs on each first-review file before the split.
- It refuses the file unless it is valid JSON covering exactly the scenario's 11 cases, each with labels A, B and C, a `score_ignoring_critical` of 0, 0.5 or 1, and `critical` as integers from 1 to 5.
- When every key is the prefix of exactly one case, it renames the top-level keys to the full case ids and changes nothing else. The original is kept as `verdicts-<key>.raw.json`.
- If the file is refused:
  - it is archived as `verdicts-<key>.rejected.json`;
  - one fresh first reviewer reviews the same sheet once more, before the split;
  - if that output is refused too, the attempt stops and goes to the owner.

**Re-check and resolution.**
- A re-check, resolution or attribution output that is missing or is not valid JSON in the instructed shape is archived as `.rejected` and redone once by a fresh agent with the same prompt.
- A second failure of the same step stops the attempt and goes to the owner.
- Attribution keeps its own rule: a missing or invalid answer counts as `memory`. That applies only after the one redo.

**Case ids.** Reviews, fix agents, reports to the developer and the developer's own notes use case prefixes only (for example "N03"). Full case ids carry a topic suffix that describes the case.

## Pass rule

This is the same as attempts 3 and 4, with totals over N and O. R4 passes when both gated arms pass.

**Report comparisons.** The report gives each arm's absolute total against two fixed figures:
- 16.5 of 22, the attempts 1–2 benchmark that the gate review used;
- 13 of 22, the lowest reference total so far (attempt 4).

It also gives what attempts 1 and 2's rule (at least 20 of 22 and no critical error) would have decided.

**Attribution after the header change.** The attribution rules are frozen and still count a reply that repeats a recalled earlier assistant statement as memory-caused, even though recall now labels such lines as not the user's decisions. This is conservative against memBrain. If such a case occurs, the report says so explicitly.

## Spending, report, evidence

- **Spending:** there is no fixed cap (owner approval of 2026-11-02). The balance is read before the attempt (292.99 CNY after attempt 4) and after each scenario.
- **Report:** `evaluations/v1-2026-11-06-final-acceptance-5.md`, with an evidence archive as in attempt 4.

## Revision 2, after two invalid runs (2026-11-06)

The first two runs under this plan were invalid ([report](v1-2026-11-06-final-acceptance-5.md)). Each time, an arm failed at startup on a fixed port that still held TIME_WAIT connections from a service that had just stopped. The runtime's port check is a plain bind, and it refuses such a port.

As this plan requires, the attempt stopped and went to the owner, who chose to fix the procedure and run again (2026-11-06).

**What changes:**
- **The run script only.**
  - Before starting any arm, it waits until all four fixed ports can be bound the same way the runtime checks them, for up to five minutes. If they never become free, it stops before any paid call.
  - Just before starting arm `P` or `E`, it checks that arm's two ports again. If that wait times out, it stops every arm it has already started.
- **The check was tested before use.** A test reproduced the failure: a port in TIME_WAIT has no listener, but cannot be bound. The new wait held until the port could be bound, after 60 to 65 seconds.
- **The reviewer of this revision** found that the diagnosis matches the code, and reproduced both the failure and the fix independently.

**What does not change:**
- the runtime, the harness, the pipeline, the review instructions, the attribution rules and the pass rule;
- scenarios N and O, which keep the hashes above. Nobody has scored, blinded or read them beyond what `validity` and `diagnose` print, so they stay held out.

**This run:**
- new, empty directories, with keys `n` and `o` as before;
- every memBrain service left from the earlier runs is stopped before it starts;
- the pre-checks are saved again.

**If this run is invalid too,** the attempt stops again and goes to the owner.

**Stop rules for this run:**
- **Before any arm of N starts.** If the script stops at the first port wait, no paid call has been made. The cause is found from socket state only (for example `/proc/net/tcp`), never from any run directory, and the script may be started again.
- **After any arm has started.** If the script stops at a port wait, or anything else makes the run invalid, every arm already started is stopped at once. The attempt then goes to the owner.

**The earlier runs are sealed:**
- The run directories from runs 1 and 2 are never scored, opened, archived or used for any decision, whatever the outcome. That includes run 1's three complete N arms and their brain directories.
- This run uses a new, empty `OUT_ROOT`, so `validity` and the pipeline only ever see its six directories.

**How run 1's failure was noticed.**
- The operator's error monitor reads each `run.log` programmatically and prints only lines matching `host error`, `Traceback` or `cap reached`. That is how the o-E startup Traceback surfaced.
- After that, only `acceptance_review.py validity` and `diagnose` were run.
- No progress line, results file or reply from runs 1 and 2 was displayed. The same error-only monitor is used in this run.

**The report.** The result of this run is added to [the attempt-5 report](v1-2026-11-06-final-acceptance-5.md). That report keeps the account of runs 1 and 2 and their cost (8.22 CNY).

**Before this run:**
- the balance is read again (284.12 CNY after run 2);
- the pre-checks are saved again, with every input's hash and the bind state of the four ports.
