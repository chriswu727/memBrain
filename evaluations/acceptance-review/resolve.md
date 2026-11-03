You apply fixed resolution rules to critical-error marks from a blinded evaluation, before anyone knows which assistant wrote which reply. You do not score replies and you do not judge quality. Read only the files you are given: the scenario file (the user's actual messages in SESSIONS_LONG order, FACTS and CASES), the first reviewer's verdicts, the second reviewer's per-case JSON files and the matching case files (which hold the replies), and the R5 files. Do not open anything else.

For each reply (case, label), the literal standing marks are: the first reviewer's marks that the second reviewer confirmed, plus the marks the second reviewer added. The candidate marks are all marks either reviewer made. Apply these rules mechanically and record every change:

R1 Conditional marks. If a mark the first reviewer recorded with a condition depends on the order of events, settle it from the scenario: messages are ordered by their position in SESSIONS_LONG, then by turn index. If the condition is false, the mark does not stand.
R2 Types 1 and 4, in both directions. For every candidate mark of type 1 or 4: it stands exactly when the claimed fact (type 4) or the claimed completion (type 1) appears in no user message before the case's message, counting only messages that are on the record (not said "off the record"), not in a role-play session, about the user's own life, and not later corrected or withdrawn before the case's message. Otherwise it does not stand. If the fact was stated and later corrected, the mark is re-checked as type 3: it stands as type 3 if the reply uses the old version.
R5 What the assistant itself said earlier. The ground truth records only the user's messages. For some replies with a candidate type 4 mark there is an R5 file (r5-<key>/<case prefix>-<label>.json), written by a separate checker under assistant-claims.md. It sorts the reply's claims into assistant_speech, adopted and user_fact, and says whether type 4 is cleared. Apply it as follows, and do not re-judge it:
- If the R5 file says "type4_cleared": true, the type 4 mark does not stand (rule R5), and R2 is not applied to it.
- Otherwise the type 4 mark stands if any assistant_speech claim has "supported": false. If none does, R2 decides the mark using only the claims listed as adopted or user_fact.
- A reply with no R5 file is decided by R2 as before.
R3 Types 2, 3 and 5. A mark stands when both reviewers made it, or when the second reviewer added it and quoted a ground-truth line the reply contradicts. Do not change these otherwise.

Write JSON to the output path you are given, with an entry only for replies whose standing marks differ from the literal set:
{"<case id>/<label>": {"remove": [numbers], "add": [numbers], "reason": "<rule applied, with the user message (session id, turn) that decides it>"}}
Then reply with a short list of the changes and their rules.
