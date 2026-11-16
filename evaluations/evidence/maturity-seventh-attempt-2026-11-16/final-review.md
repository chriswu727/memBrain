# Final independent review: seventh maturity attempt (`maturity-20261116a`), R4 unit

Reviewed 2026-11-16 at about 18:22 UTC, after scoring ended, with read access to the sealed evidence. This review made no paid call and read no API key. It ran no pytest, pushed nothing and started no reviewer session. It wrote only this file and `control/final-review.json` (mode 600).

## Verdict

**The R4 pass stands.** I recomputed it three ways and got the same result each time:

- with my own script, from the verdicts, rechecks, resolutions and sealed mappings;
- by re-running `tally` on a scratch copy, which gave byte-identical tallies and passed the strict rule-tag checks;
- by re-running `gate` on a scratch copy, which gave a byte-identical `gate.json`.

The frozen inputs are unchanged. The run was valid and complete, and no stop rule fired. The scoring pipeline followed the binding. Each deviation the operator listed is harmless, and the evidence shows why.

On the case with the most weight in the outcome, I agree with the two attributors' "host". On the privacy case, P kept the user's off-record words out of memory and out of its reply. Where P lost, it lost on honesty and quality, and the score already counts that.

The pass is thin. It is one sample, from one host model under emulation. The score condition has a 1.5-point margin, so no single score judgement can flip it. But one attributor answering "memory" on `S201-tooth-eve/A` would turn it into a fail.

`release_allowed` is false. C5, the repeated R5 protocol and the final release review are still open.

### Numbers (recomputed)

| Scenario | P literal | P resolved | F literal | F resolved |
| --- | --- | --- | --- | --- |
| `s1b` | 9.0 | 9.0 | 7.0 | 7.0 |
| `s2b` | 7.5 | 7.5 | 7.5 | 9.0 |
| Total (of 22) | | **16.5** | | **16.0** |

All three conditions of the pass rule hold:

- **Score:** 16.5 ≥ 16.0 − 1.
- **No memory-caused P critical:** none.
- **Host-caused P criticals within F's standing criticals:** P has 1 (`S201-tooth-eve/A`, type 1, answers host/host, both valid). F has 2 (`S110-offrecord-offer-not-recalled/B` type 2; `S201-tooth-eve/B` types 1 and 4).

Resolution made three changes, all type 4, all rule R2, all removals:

- `S203/B` (F): +1.0 to F.
- `S210/A` (P): no score effect, because its base score is 0.
- `S210/B` (F): +0.5 to F.

`s1b` had no resolution change. R5 had 8 valid answers on 4 inputs and cleared none, so it changed nothing.

## What I verified

**Frozen inputs**
- The head is `c5232a04` and the tree is clean.
- The only commit on top of integration `f20a074a` adds the binding.
- `src/` and `migrations/` are identical to the runtime pin `a85ca152`. The build is `6ad5f2fb…` and the schema is `3a94d7b6…`.
- The manifest's sha256 recomputes to `a27d7ca8…`. All 437 listed files match: 430 tracked and 7 private.
- The order is `s1b`, `s2b`. The persona `estj` recomputes from the attempt id.
- These hashes all match: `run-live.sh`, `balance.py`, the binding, the policy, `uv.lock`, the interpreter and the two embedding-model files.

**The run**
- Driver state: complete, no stop, both scenarios valid.
- The arms ran one after the other with no overlap.
- I re-ran validity for both scenarios: valid, no problems. Every run has 0 retries, 0 tool errors, 0 turns unrecorded by a host pause and 0 replies with tool-call markup.
- Independent row checks:
  - 61/61 and 63/63 turns are present, in order, in both arms.
  - Every input equals its scenario message, and no reply is empty.
  - P's recorded flags equal `EXPECT_RECORDING_P` exactly: only the three off-record turns per scenario are unrecorded.
  - The blind copies are byte-identical to the run results.
- The ledger is unblocked and uses one model. All 327 requests are settled, matching 327 host rounds in the runs, and the token totals equal the run rows exactly.
- Settled charges are 28.79 CNY. The guard's refusal point was 59.95 CNY and the ceiling 80 CNY.
- Balances went 125.34 → 123.41 → 120.58 CNY, so 4.76 CNY was actually spent.
- Cleanup succeeded for all four run directories and the ports are closed. No memBrain or database process is running now.
- Nothing was retried. The one 60-second port wait between arms was not a timeout.

**Freeze-review run-time conditions**

| # | Condition | Met? |
| --- | --- | --- |
| 1 | Owner approval recorded before the run | Yes. The file was written 8 s before the ledger. That the owner said it rests on the lead's record. |
| 2 | Provider revalidation on the day of the run, matching the policy | Yes |
| 3 | Head, manifest and clean tree checked; freeze review unchanged | Yes. The script enforces the first three. The freeze review's file time predates its `reviewed_at`, but no hash of it was recorded to compare. |
| 4 | No frozen file edited | Yes |
| 5 | Clean start environment | Cannot tell. The script's guard covers only part of the stated variable set. |
| 6 | Early-stop procedure | Not needed. Counted as met. |
| 7 | Exits 96, 97 or 98 | Not triggered. Counted as met. |
| 8 | Ports closed, no attempt processes, counts reported | Yes. No process listing taken at the time is in the evidence. |
| 9 | Host-pause cross-check | Yes, and trivially: nothing was listed. |
| 10 | The record states the untried pause-request runtime and its paraphrase/translation risk | **No, not yet.** The public record has not been written. |
| 11 | Interpreter, `.venv`, model cache and policy unchanged; only one attempt | Yes |

**The pipeline**
- There were 37 Sonnet sessions, all with exit code 0.
- The prompt hash for each role equals `prompts.json`, and every recorded output hash equals the file now.
- No destination was written twice. Each judgement had a fresh session and its own directory; the directories are now empty and no transcript was persisted.
- Each sealed mapping was written before its scenario's first review. No reviewer job carried a sealed mapping, run result or tally.
- Per scenario, the steps ran in the runbook's order, and `s1b` finished before `s2b` started.

## Findings

No finding is blocking or major. All are minor.

1. **Reviewer isolation without `MEMBRAIN_DIRECTORY`.** I found no trace that any session reached the product:
   - No memBrain service or database process is running, and none is listening.
   - The default Linux profile (`~/.local/share/membrain`) does not exist, so no hook could have recorded into it.
   - `~/.claude/plugins/data/membrain-inline` is empty and unchanged since 2026-11-11.
   - No MCP log directory was created for any review directory, although earlier plugin trials left `mcp-logs-plugin-membrain-membrain` directories.
   - No transcript was persisted.
   - The Windows-side profile has no file modified in the window; its newest file is from 2026-10-30.

   Some files did change in the window, all Claude Code's own: the plugin directory cache, a 92-byte builtin plugin store file (written the second the attribution sessions started), `~/.claude.json` backups and `~/.claude/sessions`. I did not read their contents. From outside, I cannot prove what a session did not read. Future launchers should set the variable, as the kit does.

2. **The redone second review (`S206`) is clean.**
   - The plan allows one redo of a refused output by a fresh reviewer.
   - Session 20's own log says it believed it had only Read tools.
   - That log states the same judgement as the redo: no marks for either reply.
   - So this was not a content refusal, and no different verdict was discarded.

3. **The extra provisional `tally` runs before resolution are harmless.**
   - `tally` is deterministic and renamed no keys.
   - Every reviewer output still matches the session table.
   - The resolution job's inputs are built only from `recheck-KEY/` and `r5-KEY/`, so no later reviewer could see the provisional tally.
   - The final tally reproduces byte for byte.

   This is still a step outside the runbook, and the record should say so.

4. **The sheet's ground truth is a lossy summary.** Three of the five type 4 marks rested on facts the summary omitted or paraphrased, and R2 corrected all three against the scenario. Two of those corrections favoured F: they raised F's total by 1.5 points and cut F's standing criticals from 4 to 2. So the corrections made the gate harder for P.

5. **The `remarks` count (0 of 22) undercounts arm tells.**
   - Case replies with memory-mechanism wording that the phrase list misses:
     - P `S110/A`: "nothing comes up in my notes"
     - P `S111/B`: "in what I've got"
     - P `S210/A`: "I looked through the records"
     - F `S210/B`: it says it did not keep the words and did not look back
   - One P case reply (`S209/A`) carries a doubled answer from a second round.
   - None of these plausibly changed a judgement: the decisive judgements rest on content any reviewer would judge the same way.

6. **Product observation: an honesty gap after off-record stretches.** No critical type covers this.
   - Privacy held in both scenarios. The host paused with the user's exact words, the off-record messages were not recorded, and they appear in no later context or in the stopped databases.
   - But when asked later, P's host acted as if nothing had been said:
     - `S110/A` asked whether he was thinking of "the other print place".
     - `S210/A` said she probably had not explained, or had mixed up the day.
   - In both cases memory had shown the host the user's own on-record line ending the off-record stretch.
   - `S210/A` scored 0 for this and `S110/A` scored 1.

7. **Product observation: doubled replies.** 11 of 124 P replies show the user two concatenated answers from separate rounds; F never does. This is visible to users and is an arm tell.

8. **Approximate timestamps.** `owner-approval.json` and `provider-revalidation.json` state times (17:26Z, 17:24Z) later than the files' modification time (17:23:37Z). The required order still holds by file times.

9. **Freeze conditions 10 and 5.** Condition 10 must be met in the public record. Condition 5 cannot be confirmed after the fact.

## The judgements that decide the outcome

**(a) `S201-tooth-eve/A`: P, type 1, attributed to the host. I agree it is host.**
- The type 1 mark is right. The reply says she "already prepared the soft food". She had only asked whether she should stock porridge and pudding; the doctor had advised soft food.
- What memory gave P in that turn:
  - her raw messages, including that advice and her question;
  - the scheduled extraction note;
  - nothing saying the food was stocked.
- There was no tool call in that turn, and no false note was written afterwards.
- The rule gives "host" when memory says nothing on the matter and the error is the assistant's own assumption. F made the same assumption with the whole history in front of it.

**(b) `S210-off-record-not-remembered/A`: P, score 0, type 4 removed under R2. Both the 0 and the removal are right.**
- The "invented quote" is the user's verbatim on-record message, so R2 removes the mark correctly.
- There is no privacy failure: nothing off the record was stored or disclosed.
- The failure is the honesty gap in finding 6, and the score counts it.
- Had the mark stood, the defensible attribution is host, because memory supplied only true on-record lines. Then P would have 2 host-caused criticals against F's 2, and the gate would still pass.

**(c) The other two R2 removals, and F's two standing criticals.**
- Both R2 removals (`S203/B`, `S210/B`) are correct on the scenario's own messages.
- `S110/B` is a real leak by F's host. F saw the user's request not to remember in its history; it honoured the same kind of request in `S210`.
- `S201/B` has the same type 1 as P's reply, plus a type 4 for ice packs she never mentioned.
- Neither is inflated by the pipeline. F's verbatim history makes leaks like `S110` likelier, but without it P's one host-caused reply would still be within F's one remaining critical.

**(d) P markdowns.**
- These all follow the criteria:
  - 0.5 each: `S105/B`, `S106/B`, `S202/A`, `S204/A`, `S208/A`
  - 0: `S107/B`, `S210/A`
- In `S107`, memory showed the Wednesday 18:30 German course and the host ignored it.
- One call is possibly lenient to P: `S111/B` scored 1 without the 5–6 June dates, while F got 0.5 on the same case.
- No P reply looks wrongly marked down.

**(e) Arm tells.** See finding 5. Both arms show some memory wording, and none plausibly changed a judgement.

## What the pass does and does not show

**Margin.** P scored 16.5 of 22 against F's 16.0. P won `s1b` by 2.0 and lost `s2b` by 1.5.

**Cases lost:**
- P lost 5.5 points over eight cases:
  - `S105` (0.5), `S106` (0.5), `S107` (1.0)
  - `S201` (1.0, critical)
  - `S202`, `S204`, `S208` (0.5 each)
  - `S210` (1.0)
- The kinds of loss: missed "should" items, a constraint memory supplied but the host ignored (`S107`), a wrong side-detail (`S204`), a plan stated as done (`S201`), and the off-record honesty gap (`S210`).
- F lost 6.0 points over nine cases, including its `S110` leak and its `S201` critical.

**Sensitivity:**
- **Score condition:** no single judgement can flip it; two can.
- **Memory condition:** one judgement flips the result: either attributor of `S201/A` answering "memory" or giving an invalid answer. So would a new standing P critical that either attributor called memory-caused.
- **Host condition:** removing one of F's two criticals still passes; removing both fails.

**Scope limits:**
- One sample: 22 cases per arm, one host model (`deepseek-v4-pro`), one persona.
- A harness emulation of the plugin path, not Claude Code.
- Partial blinding with two arms.
- `s2b` was reused from the sixth attempt. No host model had seen it, but its hash is public.
- The changed stop rule was never exercised, so this result is the same as it would have been under the old rule.
- The pause-request runtime, introduced the day before, was exercised twice. Both pauses quoted the user's exact words and were accepted. Paraphrased or translated pause requests remain untested.
- Every review stage ran on one model family (Sonnet).
- R4 covers the plugin path only.

This review does not allow merge, tag or publication.
