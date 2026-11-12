# The host AI can ask for its own earlier replies, and the embedding model loads when the service starts

Base: pin `59c6bc63` (runtime `75f50fd`). Runtime commits `bbeb3ab3` and `fa88a4b2`; pin commit `5b7ec232` points all nine launchers at the latter. No migration. Two of the defects the [LongMemEval evidence run](longmemeval-evidence-recall-2026-11-12.md) pointed at. No model was called. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

## The assistant's earlier replies

**What was wrong.** Recall leaves the assistant's own earlier words out unless the question is recognised as asking about them, and it recognised that by a short list of phrasings. Ordinary questions ("the two companies you mentioned", "you told me", "remind me of that deli") are not on the list, so the evidence of such questions was almost never shown: 2 of 10 in the LongMemEval sample, and 1 of 5 in the answer sample of 2026-10-29, where it was first recorded.

**Why the rule is there.** In the acceptance run of 2026-11-07 a host presented a suggestion the assistant had once made, a folding stool, as something the user's mother owned, although the line was marked as the assistant's ([R11-B](v1-2026-11-07-final-acceptance-6.md)). Showing the assistant's replies to everything that matches them would bring that back.

**What changed, by the owner's choice among three options.** Automatic recall is as it was. The judgement moves to the host AI, which can tell that the user is asking about something it said:

- The recall tool has a new option, `my_replies`. With it the assistant's earlier replies are searched as well and come back marked "assistant said".
- The session notice and the plugin skill tell the host AI that its earlier replies are not shown unasked, and to search with that option when the user asks about something it said, recommended or explained.
- Hosts whose tools lack the option (OpenClaw, AstrBot, the proxy) are not told and behave as before.

**Measured**, on 30 LongMemEval questions outside the first sample, their histories stored once and asked again ([rows](longmemeval/results-2026-11-12/)): share of questions with all their evidence shown.

| | Questions | Automatic recall block | The recall tool with `my_replies`, the question as its query | Either |
| --- | --- | --- | --- | --- |
| All | 30 | 73.3% | 80.0% | 86.7% |
| Assistant's words | 5 | 40% | **100%** | 100% |
| One session, user's words | 5 | 80% | 100% | 100% |
| Several sessions | 5 | 100% | 80% | 100% |
| Temporal reasoning | 5 | 60% | 40% | 60% |
| Knowledge update | 5 | 100% | 100% | 100% |
| A preference | 5 | 60% | 60% | 60% |

- The automatic block is unchanged from before the change (73.3% on the same questions).
- With the option, the evidence of all five questions about the assistant's words is returned. On other kinds of question the assistant's replies take room from the user's messages, which is why the option is for the host to set and not on by default.

**Not measured: whether a host makes the call.** The table shows what the tool returns if it is asked. Whether Claude Code or Codex, reading "remind me of that deli you mentioned", searches with the option set, and whether the folding-stool error stays away, needs an answer run with a host model and a judge. That is a paid step for the owner to approve.

## Warm-up

The [first version](longmemeval-evidence-recall-2026-11-12.md) of the LongMemEval report said recall took two seconds on a larger history. It was the first recall after each service start, which loaded the local embedding model. The model is now loaded in the background when the service starts.

On a stored history of 472 turns, through the real service: before, the first recall took 2.2 seconds and later ones about 0.5. Now the first takes 0.68 seconds when asked four seconds after the service is ready, and 1.3 seconds when asked the instant it is ready, while the model is still loading. A metered embedding provider is not touched, and a model that is not installed yet is left alone.

## Verification

- **Full local source suite on the pin commit `5b7ec232`**, with the local embedding model: 8,535 passed, 4 skipped (the Docker journeys), **2 failed**, in 54 minutes; source and migrations unchanged during the run.
  - One failure was a test that listed the recall tool's options and did not expect the new one. Its expectation was updated in `2847822f`.
  - The other was a test that starts a real service: its database could not bind its port, because other sessions were running service tests on the same machine at that moment. Not caused by this change.
  - Both test files were then run alone, with no other service test running: 123 passed. The suite was not run again as a whole.
- New tests: the recall tool returns the assistant's replies only when asked ([test](../tests/test_recall_replies.py)); warm-up does nothing without an installed model, loads an installed one, and does not hold up the service's start ([test](../tests/test_local_embeddings_warm_up.py)).
- A lesson for running several sessions on one machine: tests that start a local service race for the same default ports. They now take turns.
