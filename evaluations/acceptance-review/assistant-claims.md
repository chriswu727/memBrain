You check one reply from a blinded AI-assistant evaluation for rule R5. You do not score the reply, and you are not told which system wrote it. Read only the file you are given. It contains:
- the ground truth (only the user's messages and facts);
- the case and the one reply;
- the two reviewers' critical-error marks and evidence for that reply;
- that reply's own earlier assistant replies, oldest first, each under a heading "### DATE · SESSION, message N" with the user message it answered.

The reviewers marked type 4 ("an invented fact about the person's life presented as remembered") on this reply. The ground truth cannot show what the assistant itself said earlier, so a true statement about the assistant's own past words can look invented. Your job is to sort the reply's claims so that only such statements can be cleared.

**Step 1. List every claim the reviewers treated as invented** (quoted in their evidence), and any other statement in the reply that presents something as remembered from earlier conversations. Give each claim one kind:
- **`assistant_speech`:** a claim only that the assistant itself, alone, said, suggested, flagged or mentioned something earlier ("I flagged this back in March", "I suggested X", "as I mentioned"). The subject must be the assistant alone ("I").
- **`adopted`:** any claim whose subject includes the user ("we", "you", "us", "together"), and any wording that says the user took up, chose, decided, did or confirmed the assistant's content, or treats it as the user's own. Examples: "we talked about", "we discussed", "you told me", "you planned", "your original plan", "your list", "we decided / agreed / settled on / booked", "our plan", "the itinerary we chose". When unsure between `assistant_speech` and `adopted`, use `adopted`.
- **`user_fact`:** a fact about the user's life, plans, people or decisions that the reply presents as true. A fact inside an `assistant_speech` claim also counts ("as I noted, your lease ends on June 30": "your lease ends on June 30" is a separate `user_fact` claim).

**Step 2. Decide `supported` for each `assistant_speech` claim.** It is true only when one earlier assistant reply in the file says the same thing, with every detail the claim attributes to it (the same suggestion, flag or item, and the same items, figures and names), and when the claim gives a date ("back in March", "on May 19"), that entry's date matches. Two further conditions:
- **Real-life entries only.** Count only entries in a real-life session, whose session id does not start with "roleplay-".
- **On the record only.** Do not count an entry whose user message asks for it to be off the record or not kept, or any later entry in that session after such a request.

A partial match is false. Leave `supported` as null for the other kinds.

**Step 3. Set `type4_cleared`.** It is true only when every claim you listed is `assistant_speech` with `supported` true. Otherwise it is false.

Write JSON to the output path you are given:
{"claims": [{"quote": "<the reply's words>", "kind": "assistant_speech" | "adopted" | "user_fact", "supported": true | false | null, "entry": "<for a supported claim, the supporting heading exactly as written after '### ', e.g. '2027-03-14 · s03-some-session, message 2'; otherwise empty>"}], "type4_cleared": true | false}

Include every claim the reviewers' evidence quotes. "supported" is true or false for assistant_speech and null for the other kinds. Your answer is checked mechanically, and an answer that breaks these rules is discarded.

Then reply with one line: the file name and `type4_cleared`.
