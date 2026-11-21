# The memory page, repaired for showing

Runtime `9a423c2d`; launcher pin: the commit that adds this record. Page files and two label functions only: no migration, no new view, control or text. It closes no release gate.

A session recording a demo from the real page listed what looked bad. Each defect was reproduced on a memory recorded through the plugin's hooks (22 user turns and 12 notes; and the same with 120 more turns), fixed, and pinned by a browser test that checks geometry and text, not pixels (17 tests; those written before the fix failed at the start commit).

| Defect | Cause | Now |
| --- | --- | --- |
| Conversation summaries and source links cut at 90 characters mid-word with no ellipsis ("…we want to hik") | two `slice(0, 90)` on the page, a second cutter that could split a surrogate pair, and map labels cut at 79 or 80 characters on the server | one function on the page and one on the server: cut at a word boundary (the browser's word segmenter, so Chinese too), never inside a character sequence, always ending in "…" |
| 3D view: area names on top of each other when rotated | a moved label was checked only against the first label it clashed with, and placed anyway after four tries | placed nearest first against every placed label; hidden until the view turns when no line is free. Checked on 89 frames of a full turn and tilt |
| 3D view: the tooltip cut off at the canvas edge | always drawn right of and below the pointer | flips side and stays inside |
| The key's "earlier note based on" row wrapped away from its sample and count | a wrapping flex row | a grid: sample, name, description, count |
| "Demo · Simulated signals" at 10 px | — | 24 to 30 px, the largest text of the showcase: it is the label that says what is not real |

## A real memory in the showcase, and what the built-in demo shows that real data does not

- **The neuron-like branches around the dots are drawn only for the built-in demo.** They stand for nothing, and a real memory never gets them.
- **The demo is richer in notes than a memory the plugin records**: 21 of its 39 records are notes; a recorded memory is mostly original messages and statements taken from them, joined by evidence lines.
- **Real messages were laid out in a small volume at the centre**: 69% of a real memory's dots lay near the centre against 23% for the demo. The volume now fills the middle of the shell (23% and 17% for the two recorded memories). Nothing is drawn that is not a record or a recorded link.

## Not fixed

- While the full-screen showcase runs, nothing on screen says that the brain shape and the demo's branches are decoration (the footer that says so is hidden).
- Statements taken from messages are listed with labels such as "assistant assistant (direct_statement): …": the stored text, not a cut made by the page.
- Server-side labels of Chinese text without punctuation are cut between characters, not words.
- Seen in headless Chromium on Linux with software WebGL only.

## Verification

Full local suite, sharded over two workers: 5,118 passed, 2 failed, 11 strict expected failures, 4 skipped. The two: the pin test, by design before the pin (it passes with this commit), and one recall test known to give different results on the same commit, under investigation.
