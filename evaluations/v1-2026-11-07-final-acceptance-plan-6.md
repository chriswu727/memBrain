# Final behavioral acceptance plan (R4), attempt 6, frozen before any paid call

[Attempt 5](v1-2026-11-06-final-acceptance-5.md) did not pass:
- **Plugin arm `P`:** 19 against the reference's 17.5, but it had three memory-caused critical replies.
- **Proxy arm `E`:** 16, below the reference minus 1. All three of its critical replies were host-caused.

Of the plugin arm's three memory-caused replies:
- **Two were true references to the assistant's own earlier replies.** The reviewers' ground truth records only the user's messages, so it could not confirm them.
- **One was a real note problem:** a paid-for purchase with a future delivery date had been saved as done.

**On 2026-11-06 the owner chose to fix both problems and run again.**
- The product fix goes into the runtime.
- The scoring fix is a new resolution rule, R4, which applies from this attempt on and to every arm alike.

Wherever this plan does not say otherwise, [attempt 5's plan](v1-2026-11-06-final-acceptance-plan-5.md) applies in full, including its Revision 2. That covers the arms, running and keys, the run script, the validity check before scoring, the reading rule for an invalid run, the stop rules, the checks on review outputs, case-prefix-only reporting, attribution, the pass rule and the report comparisons.

## Candidate

- **Runtime.** Commit `a5511008dce080ecb91e27e7833102197a7dbf31`. Commit `cbcac0f` re-pins every launcher to it; that commit changes only the nine launcher files.
- **Install check.** The release install check passed 17 of 17 on this runtime, upgrading from attempt 3's runtime `9a1816a` ([results](release-install-2026-11-07.json)). The upgrade from attempt 5's runtime `b6d725a` was not run separately: the two runtimes differ only in how notes are rendered and in the note guidance texts.
- **Freeze.** The runtime, the harness, the pipeline, the run script, the review instructions and the scenarios are frozen at the hashes below from the first paid call until scoring ends.
- **Before the first paid call**, the outputs of these checks are saved:
  - the pin check reports 2 passed;
  - `git status --porcelain` is empty;
  - `git diff a551100 -- plugins/membrain/skills src/membrain` is empty;
  - `MEMBRAIN_SRC` is unset, and `membrain.__file__` resolves into this checkout;
  - the bind state of the four ports;
  - every input's hash.

**Every runtime change since attempt 5's runtime `b6d725a`** (`git diff b6d725a a551100 -- src plugins integrations`):
- **Done with a date still ahead.** A note of kind `plan` or `agent_commitment` with status `done` and an `occurs_at` date after today now reads "done so far; on DATE is still ahead, so that has not happened yet". A `done` note whose `due` date is still ahead is unchanged, because that is a deadline met early.
- **What done means.** The note tool description, the skill, AstrBot's and OpenClaw's note tool texts, and the note-extraction instructions now say that done means everything in the note has happened: a purchase paid for but not yet delivered, or a booking still ahead, is scheduled, with its date. This changes what the host is told in arm `P`, and what the extraction model is told in arm `E`.
- **Launchers.** In this diff the launchers pin `b6d725a`. The pin to `a551100` comes from commit `cbcac0f`, which is not part of the diff.
- **Tests:** `tests/test_typed_notes.py` covers a future event date, a past date, today's date and a deadline met early.

## Scoring change: rule R4 (owner-approved, from this attempt on)

- **The problem.** The ground truth records only what the user said. A reply's true statement about what the assistant itself said earlier ("I flagged this back in March") therefore looked invented, and type 4 marks stood on it. This decided attempt 3's J07-C and attempt 5's N06-C and N08-C.
- **The pipeline change.** `acceptance_review.py split` now also writes `recheck-<key>/assistant/<case>-<label>.md` for every case and label. Each file holds that label's own earlier assistant replies, oldest first, dated, and up to the case's message. The files do not name the arm, so blinding is kept.
- **The rule.** [resolve.md](acceptance-review/resolve.md) gains R4. For a type 4 mark whose claimed fact is about what the assistant said, suggested, flagged or discussed earlier:
  - the mark does not stand when that label's file contains the statement in substance before the case's message, and stands otherwise;
  - R4 does not apply, and R2 decides as before, when the reply presents the assistant's words as the user's own words, plan or decision ("your original plan"). This is the case of attempt 4's M06-C.
- **Scope.** R4 applies to every arm alike, the reference included.
- **Unchanged:** the first-review, re-check and attribution instructions, and the pass rule. The resolution reviewer is also given the per-label files.

## Inputs

| File | SHA-256 |
| --- | --- |
| [Scenario Q](v1-2026-11-07-acceptance-scenario-q.py), mainly English with one session in Spanish | `09b703ad4a9fb147020edc63910e7f95084fb75e9944f046135504050ed9021f` |
| [Scenario R](v1-2026-11-07-acceptance-scenario-r.py), mainly Chinese with one session in English | `fcb27896c4ef487035729649fc60e1e7c6a432d50201f4b91edcbcdd6c6bd37e` |
| [Harness](v1-2026-10-29-phase-b-harness.py) (unchanged) | `65a2dc5e7ba2e79caff4a11ce2775c287a2f41e1e7fe35fd4662fc1ada58f5a3` |
| [Run script](v1-2026-11-05-run-scenario.sh) (unchanged since attempt 5's Revision 2) | `82e4cf00766de874fe9154aa3d16fa6d794b59f1439bf8ee123930dc2a16cdf6` |
| [Blinding](v1-2026-10-29-phase-b-blind.py) | `320b8c2d55e7551c90ee229079b352da8d24e360fa42f6b2cb1c54dbfcc887d6` |
| [Date pre-check](v1-2026-11-02-date-precheck.py) | `3e04a9915df6b52351806ebf4bb9ec8c368875762d94140071f4284b832065a6` |
| [Review pipeline](acceptance_review.py) (split writes per-label assistant replies) | `aeb0d73bf27287f88c25f17bbf5f1d4f55e0fdc7cca83275a12960e660f7f0e7` |
| [First-reviewer instructions](acceptance-review/first.md) | `4bc86a35139ba297d62a46fa90b2600440a04a6f30a2d02480344e4f337475a6` |
| [Re-check instructions](acceptance-review/recheck.md) | `7f1efbbe87e8087962bdd2a3c2ebdd237900c7b7155188450c512dc1b734c4da` |
| [Resolution instructions](acceptance-review/resolve.md) (adds R4) | `c30f9e2479438e16b11ba23738f1f1a90e4dfe0855e71e978c9860d42f7f44d4` |
| [Attribution instructions](acceptance-review/attribute.md) | `737865ae9e982b19c242d26e6a1865e8f136cc686eb72f9e2230652ffc97648f` |

## Scenarios

- **Who wrote Q and R.** A fresh agent wrote each one under the same brief and restrictions as N and O. Neither agent was allowed to open any earlier acceptance scenario (F onwards), any result, or anything about the product.
- **N and O have been scored and read**, so they are not used again.
- **What the developer has seen of Q and R:** only their hashes, the date pre-check's last line, and the case prefixes and fix counts the reviews report.
- **Scenario fixes** are handled as before. An independent reviewer writes the scenario findings to a file the developer does not open, and an agent other than the developer applies the required fixes. The final hashes are recorded here, and the date pre-check is re-run on Q and R, with only its last line shown to the developer.

## Running and keys

- **Order and keys.** Q runs first, then R, with keys `q` and `r`, in a new, empty `OUT_ROOT`.
- **Before the run**, every memBrain service left from earlier attempts is stopped.
- **Monitoring.** The operator's monitor prints only `host error`, `Traceback` and `cap reached` lines.

## Pass rule

This is the same as attempts 3 to 5, with totals over Q and R. R4 passes when both gated arms pass.

**The report gives:**
- the absolute totals against 16.5 (the attempts 1–2 benchmark) and against 13 (the lowest reference total so far);
- what attempts 1 and 2's rule would have decided;
- each mark that R4 removed, with its case prefix and label.

## Spending, report, evidence

- **Spending:** there is no fixed cap (owner approval of 2026-11-02). The balance is read before the attempt (268.69 CNY after attempt 5) and after each scenario.
- **Report:** `evaluations/v1-2026-11-07-final-acceptance-6.md`, with an evidence archive as in attempt 5.
