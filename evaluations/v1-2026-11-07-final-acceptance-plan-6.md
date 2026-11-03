# Final behavioral acceptance plan (R4), attempt 6, frozen before any paid call

[Attempt 5](v1-2026-11-06-final-acceptance-5.md) did not pass:
- **Plugin arm `P`:** 19 against the reference's 17.5, but it had three memory-caused critical replies.
- **Proxy arm `E`:** 16, below the reference minus 1. All three of its critical replies were host-caused.

Of the plugin arm's three memory-caused replies:
- **Two were true references to the assistant's own earlier replies.** The reviewers' ground truth records only the user's messages, so it could not confirm them.
- **One was a real note problem:** a paid-for purchase with a future delivery date had been saved as done.

**On 2026-11-06 the owner chose to fix both problems and run again.**
- The product fix goes into the runtime.
- The scoring fix is a new resolution rule, R5, which applies from this attempt on and to every arm alike. It is named R5 so that it cannot be confused with the release gate R4.

Wherever this plan does not say otherwise, [attempt 5's plan](v1-2026-11-06-final-acceptance-plan-5.md) applies in full, including its Revision 2. That covers the arms, running and keys, the run script, the validity check before scoring, the reading rule for an invalid run, the stop rules, the checks on review outputs, case-prefix-only reporting, attribution, the pass rule and the report comparisons.

**Review history.**
- A first independent reviewer approved a draft with eight required plan fixes and four required scenario fixes.
- A second reviewer checked the reworked rule. It approved with four more required fixes, and recommended two checkers per reply.
- This version makes every required fix and adopts that recommendation. Agents other than the developer applied the scenario fixes.

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
- **Done with a date still ahead.** A note of kind `plan` or `agent_commitment` with status `done` and an `occurs_at` date after today now reads "done so far; on DATE is still ahead, so that has not happened yet". When the note also has a `due` date, the tag reads "done so far; due DUE, on DATE is still ahead, so that has not happened yet". A `done` note whose `due` date is still ahead is unchanged, because that is a deadline met early.
- **What done means.** The note tool description, the skill, AstrBot's and OpenClaw's note tool texts, and the note-extraction instructions now say that done means everything in the note has happened: a purchase paid for but not yet delivered, or a booking still ahead, is scheduled, with its date. This changes what the host is told in arm `P`, and what the extraction model is told in arm `E`.
- **Launchers.** In this diff the launchers pin `b6d725a`. The pin to `a551100` comes from commit `cbcac0f`, which is not part of the diff.
- **Tests:** `tests/test_typed_notes.py` covers a future event date, a past date, today's date and a deadline met early.

## Scoring change: rule R5 (owner-approved, from this attempt on)

**The problem.** The ground truth records only what the user said. A reply's true statement about what the assistant itself said earlier ("I flagged this back in March") therefore looked invented, and type 4 marks stood on it. This decided attempt 3's J07-C and attempt 5's N06-C and N08-C.

**The procedure**, between the re-checks and resolution, for every arm alike:
1. **Inputs.** `acceptance_review.py r5-inputs REVIEW_DIR BLIND_DIR SCENARIO KEY r5-inputs-<key>/` writes one file per reply that has a candidate type 4 mark from either reviewer. Each file holds:
   - the ground truth, the case and that one reply;
   - both reviewers' marks and evidence for that reply;
   - that reply's own earlier assistant replies, oldest first, up to the case's message, each under a heading "DATE · SESSION, message N" with the user message it answered.

   A file is named by case prefix and label only, and holds no other label's reply or history. The command writes nothing unless it completes, refuses an existing folder, and fails if any earlier turn is missing from the results.
2. **Two fresh checkers per file**, independently, apply [assistant-claims.md](acceptance-review/assistant-claims.md). They write `r5-answers-<key>/<prefix>-<label>.1.json` and `.2.json`.
   - Each checker lists the claims the reviewers flagged and gives each a kind:
     - `assistant_speech`: only that the assistant alone ("I") said, suggested, flagged or mentioned something;
     - `adopted`: any "we", "you" or "us" subject, or any wording that makes the assistant's content the user's own. When unsure, `adopted`;
     - `user_fact`: any fact about the user's life presented as true, including one inside an `assistant_speech` claim.
   - An `assistant_speech` claim is `supported` only when one earlier entry says the same thing with every detail attributed to it, and with the same date when the claim gives one.
   - Only real-life entries count (not `roleplay-` sessions), and only entries on the record.
3. **`acceptance_review.py r5-check r5-inputs-<key>/ r5-answers-<key>/ r5-<key>/`** checks every answer mechanically.
   - An answer is invalid unless it is valid JSON with at least one claim, every kind is one of the three, `supported` is a boolean exactly for `assistant_speech`, every supported claim names an existing real-life heading of its input file, and `type4_cleared` is true exactly when every claim is a supported `assistant_speech` claim.
   - An invalid answer is set aside as `.rejected` and redone once by a fresh checker. A second invalid answer counts as not clearing.
   - The command then writes `r5-<key>/<prefix>-<label>.json` with only `{"type4_cleared": …}`. It is true only when both answers are valid and both clear the mark.
4. **Resolution** ([resolve.md](acceptance-review/resolve.md)) gets only the `r5-<key>/` results, never the inputs or the answers, so it cannot link labels across cases.
   - If `type4_cleared` is true, the type 4 mark does not stand, and R2 is not applied to it.
   - In every other case R2 decides exactly as before.
   - For every reply with a result, the resolution reviewer also records what R2 alone would have decided.
   - The resolution reviewer is also given the per-case files, which hold the replies.

**What R5 can and cannot do:**
- **It can only remove a whole type 4 mark.** It never adds a mark or keeps one that R2 would remove.
- **It cannot clear a fact about the user,** even inside a reference to the assistant's words.
- **It cannot clear "we"/"you" wording, or the assistant's words presented as the user's.** That is attempt 4's M06-C pattern, which stays with R2.

**The report gives,** for every reply with an R5 result, that result and what R2 alone would have decided.

**Unchanged:** the first-review, re-check and attribution instructions, and the pass rule.

## Inputs

| File | SHA-256 |
| --- | --- |
| [Scenario Q](v1-2026-11-07-acceptance-scenario-q.py), mainly English with one session in Spanish | `f7712de9ab3e51b9338d09f935bf9dd6457788113f94ae43a5754f207580141b` |
| [Scenario R](v1-2026-11-07-acceptance-scenario-r.py), mainly Chinese with one session in English | `682be30e6793167c7bc5c6f9f563e3f1cf727912bae9352128bd8c977b7de7ae` |
| [Harness](v1-2026-10-29-phase-b-harness.py) (unchanged) | `65a2dc5e7ba2e79caff4a11ce2775c287a2f41e1e7fe35fd4662fc1ada58f5a3` |
| [Run script](v1-2026-11-05-run-scenario.sh) (unchanged since attempt 5's Revision 2) | `82e4cf00766de874fe9154aa3d16fa6d794b59f1439bf8ee123930dc2a16cdf6` |
| [Blinding](v1-2026-10-29-phase-b-blind.py) | `320b8c2d55e7551c90ee229079b352da8d24e360fa42f6b2cb1c54dbfcc887d6` |
| [Date pre-check](v1-2026-11-02-date-precheck.py) | `3e04a9915df6b52351806ebf4bb9ec8c368875762d94140071f4284b832065a6` |
| [Review pipeline](acceptance_review.py) (adds `r5-inputs`) | `0f9c0c2729cb78f9c583c16d092aebeb9d6b07c1a5d46295c495bf92a2b4dd0e` |
| [First-reviewer instructions](acceptance-review/first.md) | `4bc86a35139ba297d62a46fa90b2600440a04a6f30a2d02480344e4f337475a6` |
| [Re-check instructions](acceptance-review/recheck.md) | `7f1efbbe87e8087962bdd2a3c2ebdd237900c7b7155188450c512dc1b734c4da` |
| [Resolution instructions](acceptance-review/resolve.md) (adds R5) | `31c7568d1607ccf068f115502f1dba4a04ba4d7449ca102d8256b31d44fa27f2` |
| [R5 checker instructions](acceptance-review/assistant-claims.md) (new) | `d2fab14c18e0c7804ce678badbb7fc74479413741ea9ab4540b1bedd6b7d4d11` |
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
- **If the run is invalid** for any reason, including a port wait that stops after an arm has started:
  - every started arm is stopped at once;
  - nothing is scored;
  - `diagnose` is the only reading;
  - the attempt goes to the owner, as attempt 5's Revision 2 set out.

  There is no automatic re-run.

## Pass rule

This is the same as attempts 3 to 5, with totals over Q and R. R4 passes when both gated arms pass.

**The report gives:**
- the absolute totals against 16.5 (the attempts 1–2 benchmark) and against 13 (the lowest reference total so far);
- what attempts 1 and 2's rule would have decided;
- each mark that R5 removed, with its case prefix and label.

## Spending, report, evidence

- **Spending:** there is no fixed cap (owner approval of 2026-11-02). The balance is read before the attempt (268.69 CNY after attempt 5) and after each scenario.
- **Report:** `evaluations/v1-2026-11-07-final-acceptance-6.md`, with an evidence archive as in attempt 5.
