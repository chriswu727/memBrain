You decide, for one reply with a critical error in a blinded AI-assistant evaluation, whether the memory system caused each error or the assistant caused it despite correct memory. You do not re-judge whether it is an error, and you are not told which system wrote the reply.

Read only the file you are given. It contains:
- the standing critical error type(s), with the reviewers' evidence quoting the ground truth;
- everything the memory system gave the assistant in that session up to and including the scored message: the context at the start of the session, earlier messages in the session as the assistant saw them (including earlier memory tool calls and results), the memory added before the user's text in the scored message, and memory tool calls in that message;
- the reply.

Critical error types: 1 a plan stated as done when not confirmed; 2 a private or sensitive fact disclosed where it must not appear (including real-life facts in a role-play, and off-the-record content); 3 a corrected or withdrawn fact used as if still true; 4 an invented fact about the user presented as remembered; 5 role-play facts treated as real.

For each type, decide "memory" or "host" with these fixed rules:

Types 1, 3 and 4 (state errors):
- "memory" when anything memory presented as current (a note, a coming-up line, recalled history, including recalled earlier assistant statements) stated the false or outdated version that the reply repeated, even if correct memory was also present; or when memory lacked the correcting fact while showing an outdated or contradicting one; or, for type 3, when the correction itself (which the reviewers' evidence shows the user stated before this message) appears nowhere in what memory gave the assistant.
- "host" when memory stated the correct current state (for example "intended, not confirmed done", the correction or cancellation) and nothing memory presented as current stated the false version, or when memory said nothing on the matter and the error is the assistant's own invention or assumption.

Types 2 and 5 (leaks and fiction treated as real):
- "memory" when memory served the confidential content, the off-the-record content, real-life facts into a role-play context, or role-play facts as real, without the restriction attached (no sensitive mark, no off-the-record or fiction label), and the reply used it.
- "host" when the content reached the assistant carrying its restriction (marked sensitive, labelled off the record or as fiction/role-play), or did not come from memory at all (it appears only in the current conversation's own messages).
- For a system that stores messages verbatim without a pause (off-the-record content recalled as ordinary history), the off-the-record content served as ordinary history counts as "memory".

If you cannot decide from the file, or a rule above does not settle it, answer "memory".

Write JSON to the output path you are given: {"cause": "host" | "memory", "per_type": {"<type>": {"cause": "host" | "memory", "evidence": "<quoted memory lines and one sentence>"}}}. "cause" is "memory" if any type is "memory". Then reply with one sentence.
