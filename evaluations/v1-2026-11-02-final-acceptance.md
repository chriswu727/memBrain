# Final behavioral acceptance (R4), attempt 1, 2026-11-02: not passed

This attempt ran the [frozen plan](v1-2026-11-02-final-acceptance-plan.md) on runtime `2417489`. **Neither gated arm passed.** Each must score at least 20 of 22 with no critical error. The causes were found, repaired and covered by tests. Under the plan, the repaired runtime must now pass a new attempt on two new held-out scenarios. Scenarios F and G are not used for acceptance again.

## Result

Blind first-reviewer scores, after the second review of critical errors (pass 1, partial 0.5, fail 0):

| Arm | Scenario F (11) | Scenario G (11) | Total (22) | Critical errors standing | R4 |
| --- | --- | --- | --- | --- | --- |
| Plugin path (`P`) | 6 | 10.5 | **16.5** | 4 (all in F) | fail |
| Proxy with note extraction (`E`) | 9.5 | 10 | **19.5** | 2 | fail |
| Whole history in the prompt (`F`, reference) | 11 | 6 | 17 | — | not gated |

On a literal reading of the second review, without the four resolutions described under Scoring, the totals are P 16, E 17, F 16. The outcome is the same either way.

## What failed and why

**The plugin path stopped remembering after "this stays between us"** (scenario F, four critical errors).
- On February 2 the user wrote "This stays between us" before describing a private work matter. The host model called `memory_pause` with no end date.
- Every later note failed with "Recording is paused", and no later message was stored. That included "Leila said no" (about dog-sitting) and "Wren's gone vegetarian".
- Weeks later the host still asked whether Leila had agreed to dog-sit, and planned meat meals for Wren.
- The user asked for confidentiality, not forgetting. One misread request silenced memory for the rest of the scenario.
- In scenario G nothing paused memory, and the same arm scored 10.5 of 11.

**The proxy arm lost a cancellation** (F09, critical).
- Extraction did save "Leila can't dog-sit (cancelled)". But with 29 notes, that cancelled plan fell outside the notes budget, while the history block still showed the original "I'll ask Leila" message.
- The host then asked whether Leila had confirmed. Extraction saved that question back as a note, "Leila soll … aufpassen; Bestätigung steht noch aus" ("Leila is to dog-sit; confirmation still pending"). It was written in German because a German-practice preference was among the notes.

**The proxy arm put a visit in the wrong month** (G06, critical).
- On October 7 the user asked to move her mother's visit from "11号到13号" (the 11th–13th) to "16号周六" (Saturday the 16th).
- Extraction filed it as November 11–13 and November 16, a Tuesday.
- On November 15 the host told her that her mother would arrive "this Saturday, the 16th".

**Other non-passes in the gated arms** (no critical error):
- P F05: hedged on the run clearance.
- P F08: the food-day answer was partial.
- P G02: the reply gave the swim-class reminder but did not rewrite the aftercare note.
- E F07: hedged on the visit weekend.

## Repairs (commits `2304cec` and `0e1ab5e`)

- **A pause the agent starts lasts only for the conversation in progress.**
  - This covers `memory_pause` and the `membrain_pause` tools of OpenClaw, Hermes, AstrBot and `ChatMemory`. The next conversation resumes recording and says so.
  - A longer pause needs `hours`, or `until_resumed` when the user asks to stop being remembered until they say so.
  - The skill and every pause tool description say that "keep this between us" means a sensitive note, not a pause. A paused session tells the user.
- **Cancelled plans keep their place in the notes.** A cancelled plan whose date has not passed ranks with open plans, so a cancellation is not crowded out while the original plan still shows in history.
- **Extraction saves only what the person said.**
  - A question the assistant asked is not a fact.
  - Notes are written in the language of the latest exchange.
- **Extraction gets a calendar.**
  - It sees today's weekday and the next five weeks.
  - A day without a month resolves to the next matching date.
  - A date whose named weekday cannot be reconciled is left out.

## Scoring, as run

- **First review.** One fresh reviewer per scenario scored the blinded sheet. Every critical-error mark then went to a second fresh reviewer per case, who saw the case unlabelled and could confirm, reject or add marks.
- **A defect in the review tooling.**
  - The first per-case files for scenario F were cut off by a splitting bug: replies with their own `##` headings ended the case early.
  - All eleven F re-checks were run again on complete files before any label was unsealed.
  - The cut-off round is kept in the evidence as `recheck-f-invalid-truncated`.
- **Four marks resolved before unsealing**, each recorded in `resolution-f.json`:
  - **F05-A.** Both reviewers marked a corrected fact "if the update came first that day". In the scenario the update is the next turn, so the condition was false. The first reviewer had said A would then pass.
  - **F07-B.** The second reviewer added an invented-fact mark ("your long run is Sunday the 18th") but cited no ground-truth line it breaks, which the plan requires.
  - **F08-A, B and C.** The second reviewer added invented-fact marks for "your kitchen is tree-nut-free". The user had written exactly that in session s01; the ground-truth summary had left it out.
- **Scenario G** needed no resolutions. The second review there confirmed the G06 and G07 marks and added one for G09-C (a biopsy that was only scheduled, stated as done). That error is in the reference arm.

## Setup and cost

- **Runtime and checks.** Runtime `2417489`, pinned by every launcher. The pin check passed 2 of 2, and the date pre-check passed all 64 sessions.
- **Scenarios.** They were written by an agent without access to the product, then amended on the plan reviewer's instructions by a second such agent.
- **Spend.** DeepSeek spending was 27.66 CNY: 18.00 for scenario F and 9.66 for G (balance 374.77 → 347.11). The owner approved spending beyond the plan's 30 CNY cap before anything was scored.
- **Extraction.** In the extraction arm, 67 and 63 turns were read with no failure or skip, and no harness event was raised.
- **Evidence.** The [evidence archive](v1-2026-11-02-final-acceptance.evidence.tar.gz) holds:
  - per-turn results for all six runs;
  - blinded sheets and sealed mappings;
  - verdicts, re-checks (including the invalid round), resolutions and tallies;
  - reviewer instructions, the pin check and date pre-check outputs, and the balances.
